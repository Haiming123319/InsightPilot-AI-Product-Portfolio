from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


AMOUNT_KEYWORDS = ("amount", "cost", "expense", "fee", "price", "金额", "费用", "成本", "价格")
DATE_KEYWORDS = ("date", "time", "日期", "时间")


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    inferred_type: str
    dtype: str
    missing_count: int
    missing_rate: float
    unique_count: int
    sample_values: list[str]
    issues: list[str]
    semantic_type: str = ""


@dataclass(frozen=True)
class DataProfile:
    row_count: int
    column_count: int
    duplicate_count: int
    columns: list[ColumnProfile]
    issues: list[str]
    date_range: list[str] | None = None


def profile_dataframe(df: pd.DataFrame) -> DataProfile:
    duplicate_count = int(df.duplicated().sum())
    columns = [_profile_column(df[column], column) for column in df.columns]
    issues: list[str] = []

    if duplicate_count:
        issues.append(f"发现 {duplicate_count} 条完全重复记录，建议执行去重。")

    for column in columns:
        issues.extend([f"{column.name}: {issue}" for issue in column.issues])

    empty_columns = [column.name for column in columns if column.missing_rate == 1]
    if empty_columns:
        issues.append(f"以下字段全为空：{', '.join(empty_columns)}。")

    return DataProfile(
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        duplicate_count=duplicate_count,
        columns=columns,
        issues=issues,
        date_range=_infer_date_range(df),
    )


def profile_to_records(profile: DataProfile) -> list[dict[str, Any]]:
    return [
        {
            "字段": column.name,
            "识别类型": column.inferred_type,
            "原始类型": column.dtype,
            "缺失数": column.missing_count,
            "缺失率": f"{column.missing_rate:.1%}",
            "唯一值数": column.unique_count,
            "样例值": ", ".join(column.sample_values),
            "问题": "；".join(column.issues) if column.issues else "未发现明显问题",
        }
        for column in profile.columns
    ]


def _profile_column(series: pd.Series, name: str) -> ColumnProfile:
    non_null = series.dropna()
    missing_count = int(series.isna().sum())
    missing_rate = float(missing_count / len(series)) if len(series) else 0.0
    sample_values = [str(value) for value in non_null.head(5).tolist()]
    issues: list[str] = []
    inferred_type = _infer_type(series, name)

    if missing_rate > 0:
        issues.append(f"缺失率 {missing_rate:.1%}")

    if inferred_type == "金额":
        issues.extend(_detect_amount_issues(series))

    if inferred_type == "日期":
        issues.extend(_detect_date_issues(series))

    if inferred_type in {"分类", "文本"} and non_null.nunique() > 0:
        normalized_count = non_null.astype(str).str.strip().str.lower().nunique()
        raw_count = non_null.astype(str).nunique()
        if raw_count > normalized_count:
            issues.append("存在大小写或前后空格导致的疑似同义分类")

    return ColumnProfile(
        name=str(name),
        inferred_type=inferred_type,
        dtype=str(series.dtype),
        missing_count=missing_count,
        missing_rate=missing_rate,
        unique_count=int(non_null.nunique()),
        sample_values=sample_values,
        issues=issues,
        semantic_type=_semantic_type(inferred_type),
    )


def profile_to_llm_payload(profile: DataProfile, *, max_samples: int = 3) -> dict[str, Any]:
    """Build a bounded, de-identified dataset summary for intent parsing."""

    return {
        "row_count": profile.row_count,
        "date_range": profile.date_range or [],
        "columns": [
            {
                "name": column.name,
                "dtype": column.dtype,
                "semantic_type": column.semantic_type or column.inferred_type,
                "missing_rate": round(column.missing_rate, 4),
                "unique_count": column.unique_count,
                "sample_values": _safe_sample_values(
                    column.sample_values[:max_samples],
                    semantic_type=column.semantic_type or column.inferred_type,
                ),
            }
            for column in profile.columns
        ],
        "supported_task_types": ["department_summary", "department_yoy", "anomaly_detection"],
        "supported_operations": [
            "clean",
            "groupby",
            "sum",
            "year_over_year",
            "rank",
            "contribution",
            "iqr_anomaly_detection",
        ],
    }


def _safe_sample_values(values: list[str], *, semantic_type: str) -> list[str]:
    safe: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if semantic_type in {"text", "文本"}:
            safe.append("[redacted]")
            continue
        if len(text) > 40:
            text = text[:37] + "..."
        if any(token in text.lower() for token in ["@", "身份证", "手机号", "phone", "email"]):
            safe.append("[redacted]")
        else:
            safe.append(text)
    return safe


def _semantic_type(inferred_type: str) -> str:
    return {
        "金额": "currency",
        "日期": "date",
        "数值": "number",
        "分类": "category",
        "文本": "text",
        "空字段": "unknown",
    }.get(inferred_type, "unknown")


def _infer_date_range(df: pd.DataFrame) -> list[str]:
    date_columns = [column for column in df.columns if _infer_type(df[column], str(column)) == "日期"]
    if not date_columns:
        return []
    parsed = pd.to_datetime(df[date_columns[0]], errors="coerce", format="mixed").dropna()
    if parsed.empty:
        return []
    return [parsed.min().date().isoformat(), parsed.max().date().isoformat()]


def _infer_type(series: pd.Series, name: str) -> str:
    lowered_name = str(name).lower()
    if any(keyword in lowered_name for keyword in DATE_KEYWORDS):
        return "日期"
    if any(keyword in lowered_name for keyword in AMOUNT_KEYWORDS):
        return "金额"
    if pd.api.types.is_numeric_dtype(series):
        return "数值"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "日期"

    non_null = series.dropna()
    if non_null.empty:
        return "空字段"

    numeric_ratio = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce").notna().mean()
    date_ratio = pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()
    unique_ratio = non_null.nunique() / len(non_null)

    if numeric_ratio >= 0.85:
        return "数值"
    if date_ratio >= 0.85:
        return "日期"
    if unique_ratio <= 0.5:
        return "分类"
    return "文本"


def _detect_amount_issues(series: pd.Series) -> list[str]:
    text = series.dropna().astype(str)
    if text.empty:
        return []

    issues: list[str] = []
    has_currency = text.str.contains(r"[¥￥$元]", regex=True).sum()
    has_comma = text.str.contains(",", regex=False).sum()
    has_spaces = text.str.contains(r"^\s|\s$", regex=True).sum()
    cleaned = (
        text.str.replace(r"[¥￥$元,\s]", "", regex=True)
        .str.replace("人民币", "", regex=False)
    )
    invalid_count = int(pd.to_numeric(cleaned, errors="coerce").isna().sum())

    if has_currency:
        issues.append(f"金额中包含货币符号或单位 {int(has_currency)} 处")
    if has_comma:
        issues.append(f"金额中包含千分位逗号 {int(has_comma)} 处")
    if has_spaces:
        issues.append(f"金额中包含前后空格 {int(has_spaces)} 处")
    if invalid_count:
        issues.append(f"金额字段存在 {invalid_count} 个无法转换为数值的值")
    return issues


def _detect_date_issues(series: pd.Series) -> list[str]:
    text = series.dropna()
    if text.empty:
        return []

    parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    invalid_count = int(parsed.isna().sum())
    formats = text.astype(str).str.extract(r"([-/年月.])", expand=False).dropna().unique()
    issues: list[str] = []

    if invalid_count:
        issues.append(f"日期字段存在 {invalid_count} 个无法解析的值")
    if len(formats) > 1:
        issues.append("日期格式不一致")
    return issues
