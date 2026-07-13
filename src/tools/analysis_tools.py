from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.config import CleaningConfig
from src.tools.data_cleaner import clean_expense_dataframe


class AnalysisExecutionError(ValueError):
    """Raised when an analysis cannot be executed with the current data."""


@dataclass(frozen=True)
class DepartmentYoyAnalysis:
    cleaned_data: pd.DataFrame
    department_yoy: pd.DataFrame
    top_department: str
    contribution_by_type: pd.DataFrame
    monthly_trend: pd.DataFrame
    total_2025: float
    yoy_growth: float | None
    covered_rows: int
    excluded_rows: int


@dataclass(frozen=True)
class DepartmentSummaryAnalysis:
    cleaned_data: pd.DataFrame
    department_totals: pd.DataFrame
    total_amount: float
    top_department: str
    covered_rows: int
    excluded_rows: int
    data_completeness: float


@dataclass(frozen=True)
class AnomalyAnalysis:
    cleaned_data: pd.DataFrame
    anomaly_table: pd.DataFrame
    threshold: float
    q1: float
    q3: float
    iqr: float
    max_anomaly_amount: float
    covered_rows: int
    anomaly_count: int


def run_department_yoy_analysis(
    df: pd.DataFrame,
    cleaning_config: CleaningConfig | None = None,
) -> DepartmentYoyAnalysis:
    required = {"date", "department", "expense_type", "amount"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise AnalysisExecutionError(f"缺少必要字段：{', '.join(missing)}")

    cleaned = clean_expense_dataframe(df, cleaning_config)
    valid = cleaned.dropna(subset=["date_clean", "amount_clean", "department", "expense_type"]).copy()
    valid = valid[valid["year"].isin([2024, 2025])]
    if valid.empty:
        raise AnalysisExecutionError("没有可用于 2024/2025 同比分析的有效数据。")

    yearly = (
        valid.groupby(["department", "year"], as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "amount"})
    )
    pivot = yearly.pivot(index="department", columns="year", values="amount").fillna(0)
    for year in [2024, 2025]:
        if year not in pivot.columns:
            pivot[year] = 0.0

    department_yoy = pivot.reset_index().rename(columns={2024: "amount_2024", 2025: "amount_2025"})
    department_yoy["increase"] = department_yoy["amount_2025"] - department_yoy["amount_2024"]
    department_yoy["yoy_growth"] = department_yoy.apply(_safe_yoy, axis=1)
    department_yoy["status"] = department_yoy.apply(_growth_status, axis=1)
    department_yoy = department_yoy.sort_values(
        by=["yoy_growth", "increase"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)
    department_yoy["rank"] = range(1, len(department_yoy) + 1)

    top_department = str(department_yoy.iloc[0]["department"])
    top_rows = valid[valid["department"] == top_department]
    type_yearly = (
        top_rows.groupby(["expense_type", "year"], as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "amount"})
    )
    type_pivot = type_yearly.pivot(index="expense_type", columns="year", values="amount").fillna(0)
    for year in [2024, 2025]:
        if year not in type_pivot.columns:
            type_pivot[year] = 0.0
    contribution = type_pivot.reset_index().rename(columns={2024: "amount_2024", 2025: "amount_2025"})
    contribution["increase"] = contribution["amount_2025"] - contribution["amount_2024"]
    positive_increase = contribution["increase"].clip(lower=0)
    total_positive_increase = float(positive_increase.sum())
    contribution["contribution_rate"] = contribution["increase"].apply(
        lambda value: value / total_positive_increase if total_positive_increase and value > 0 else 0.0
    )
    contribution = contribution.sort_values("increase", ascending=False).reset_index(drop=True)

    monthly_trend = (
        valid.groupby(["month", "department"], as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "amount"})
    )

    total_2024 = float(valid.loc[valid["year"] == 2024, "amount_clean"].sum())
    total_2025 = float(valid.loc[valid["year"] == 2025, "amount_clean"].sum())
    yoy_growth = (total_2025 - total_2024) / total_2024 if total_2024 else None

    return DepartmentYoyAnalysis(
        cleaned_data=cleaned,
        department_yoy=department_yoy,
        top_department=top_department,
        contribution_by_type=contribution,
        monthly_trend=monthly_trend,
        total_2025=total_2025,
        yoy_growth=yoy_growth,
        covered_rows=int(len(valid)),
        excluded_rows=int(len(cleaned) - len(valid)),
    )


def run_department_summary_analysis(
    df: pd.DataFrame,
    cleaning_config: CleaningConfig | None = None,
) -> DepartmentSummaryAnalysis:
    required = {"department", "amount"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise AnalysisExecutionError(f"缺少必要字段：{', '.join(missing)}")

    cleaned = clean_expense_dataframe(df, cleaning_config)
    valid = cleaned.dropna(subset=["department", "amount_clean"]).copy()
    if valid.empty:
        raise AnalysisExecutionError("没有可用于部门费用汇总的有效数据。")

    totals = (
        valid.groupby("department", as_index=False)["amount_clean"]
        .sum()
        .rename(columns={"amount_clean": "total_amount"})
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    totals["share"] = totals["total_amount"] / float(totals["total_amount"].sum())
    totals["rank"] = range(1, len(totals) + 1)

    return DepartmentSummaryAnalysis(
        cleaned_data=cleaned,
        department_totals=totals,
        total_amount=float(totals["total_amount"].sum()),
        top_department=str(totals.iloc[0]["department"]),
        covered_rows=int(len(valid)),
        excluded_rows=int(len(cleaned) - len(valid)),
        data_completeness=float(len(valid) / len(cleaned)) if len(cleaned) else 0.0,
    )


def run_anomaly_analysis(
    df: pd.DataFrame,
    cleaning_config: CleaningConfig | None = None,
) -> AnomalyAnalysis:
    required = {"date", "department", "expense_type", "amount"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise AnalysisExecutionError(f"缺少必要字段：{', '.join(missing)}")

    # 异常分析必须先保留异常记录，否则无法识别它们。
    anomaly_config = (cleaning_config or CleaningConfig()).model_copy(update={"anomaly_action": "include"})
    cleaned = clean_expense_dataframe(df, anomaly_config)
    valid = cleaned.dropna(subset=["amount_clean"]).copy()
    if valid.empty:
        raise AnalysisExecutionError("没有可用于异常分析的有效金额数据。")

    q1 = float(valid["amount_clean"].quantile(0.25))
    q3 = float(valid["amount_clean"].quantile(0.75))
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr
    anomalies = valid[valid["amount_clean"] > threshold].copy()
    display_columns = [
        column
        for column in ["date", "department", "expense_type", "amount", "amount_clean", "employee", "project", "region"]
        if column in anomalies.columns
    ]
    anomaly_table = anomalies[display_columns].sort_values("amount_clean", ascending=False).reset_index(drop=True)
    anomaly_table["threshold"] = threshold
    anomaly_table["excess_amount"] = anomaly_table["amount_clean"] - threshold

    return AnomalyAnalysis(
        cleaned_data=cleaned,
        anomaly_table=anomaly_table,
        threshold=threshold,
        q1=q1,
        q3=q3,
        iqr=iqr,
        max_anomaly_amount=float(anomaly_table["amount_clean"].max()) if not anomaly_table.empty else 0.0,
        covered_rows=int(len(valid)),
        anomaly_count=int(len(anomaly_table)),
    )


def _safe_yoy(row: pd.Series) -> float | None:
    base = float(row["amount_2024"])
    if base == 0:
        return None
    return (float(row["amount_2025"]) - base) / base


def _growth_status(row: pd.Series) -> str:
    if float(row["amount_2024"]) == 0 and float(row["amount_2025"]) > 0:
        return "新增"
    if row["yoy_growth"] is None or pd.isna(row["yoy_growth"]):
        return "无法计算同比"
    return "可计算同比"
