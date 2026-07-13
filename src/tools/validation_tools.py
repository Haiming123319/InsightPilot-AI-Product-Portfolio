from __future__ import annotations

import math

import pandas as pd

from src.models.result import AnalysisResult
from src.models.validation import ValidationCheck, ValidationReport
from src.tools.analysis_tools import DepartmentYoyAnalysis


REQUIRED_FIELDS = {"date", "department", "expense_type", "amount"}
FORBIDDEN_CAUSAL_WORDS = ("导致", "造成", "引发")


def validate_fields(df: pd.DataFrame) -> ValidationCheck:
    missing = sorted(REQUIRED_FIELDS - set(df.columns))
    return ValidationCheck(
        check_id="field_legality",
        name="字段合法性校验",
        passed=not missing,
        severity="error" if missing else "info",
        message="字段满足当前分析要求。" if not missing else f"缺少必要字段：{', '.join(missing)}",
        details={"missing_fields": ",".join(missing)},
    )


def validate_analysis_result(
    source_df: pd.DataFrame,
    analysis: DepartmentYoyAnalysis,
    result: AnalysisResult,
    tolerance: float = 0.01,
) -> ValidationReport:
    checks = [
        validate_fields(source_df),
        validate_numeric_consistency(analysis, tolerance=tolerance),
        validate_ranking(analysis),
        validate_claim_consistency(analysis, result, tolerance=tolerance),
        validate_chart_consistency(analysis),
        validate_language_safety(result),
    ]
    return ValidationReport(passed=all(check.passed for check in checks), checks=checks)


def validate_numeric_consistency(analysis: DepartmentYoyAnalysis, tolerance: float = 0.01) -> ValidationCheck:
    total_from_departments = float(analysis.department_yoy["amount_2025"].sum())
    diff = abs(total_from_departments - analysis.total_2025)
    return ValidationCheck(
        check_id="numeric_consistency",
        name="数值一致性校验",
        passed=diff <= tolerance,
        severity="error" if diff > tolerance else "info",
        message="部门费用合计与总费用一致。" if diff <= tolerance else "部门费用合计与总费用不一致。",
        details={
            "department_sum_2025": round(total_from_departments, 2),
            "total_2025": round(float(analysis.total_2025), 2),
            "diff": round(diff, 6),
        },
    )


def validate_ranking(analysis: DepartmentYoyAnalysis) -> ValidationCheck:
    ranked = analysis.department_yoy.sort_values(
        by=["yoy_growth", "increase"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)
    expected = str(ranked.iloc[0]["department"])
    passed = expected == analysis.top_department
    return ValidationCheck(
        check_id="ranking_consistency",
        name="排名校验",
        passed=passed,
        severity="error" if not passed else "info",
        message="增长最快部门排名一致。" if passed else f"增长最快部门应为 {expected}，当前为 {analysis.top_department}。",
        details={"expected_top_department": expected, "actual_top_department": analysis.top_department},
    )


def validate_claim_consistency(
    analysis: DepartmentYoyAnalysis,
    result: AnalysisResult,
    tolerance: float = 0.01,
) -> ValidationCheck:
    problems: list[str] = []
    top_row = analysis.department_yoy.iloc[0]

    for claim in result.claims:
        if claim.metric == "yoy_growth":
            if claim.entity != analysis.top_department:
                problems.append(f"同比结论实体 {claim.entity} 与增长最快部门 {analysis.top_department} 不一致")
            if isinstance(claim.value, (float, int)) and not pd.isna(top_row["yoy_growth"]):
                expected = float(top_row["yoy_growth"]) * 100
                if abs(float(claim.value) - expected) > tolerance:
                    problems.append(f"同比结论数值 {claim.value} 与计算值 {expected:.2f} 不一致")
        elif claim.metric == "amount_2025":
            if isinstance(claim.value, (float, int)) and abs(float(claim.value) - analysis.total_2025) > tolerance:
                problems.append(f"2025 总费用结论 {claim.value} 与计算值 {analysis.total_2025:.2f} 不一致")
        elif claim.metric == "contribution_rate":
            if analysis.contribution_by_type.empty:
                problems.append("贡献率结论存在，但贡献表为空")
                continue
            first = analysis.contribution_by_type.iloc[0]
            expected = float(first["contribution_rate"]) * 100
            if claim.entity != str(first["expense_type"]):
                problems.append(f"贡献率最高类型 {claim.entity} 与计算值 {first['expense_type']} 不一致")
            if isinstance(claim.value, (float, int)) and abs(float(claim.value) - expected) > tolerance:
                problems.append(f"贡献率结论 {claim.value} 与计算值 {expected:.2f} 不一致")

    return ValidationCheck(
        check_id="claim_consistency",
        name="文字与数字一致性校验",
        passed=not problems,
        severity="error" if problems else "info",
        message="结论与结构化计算结果一致。" if not problems else "；".join(problems),
        details={"problem_count": len(problems)},
    )


def validate_chart_consistency(analysis: DepartmentYoyAnalysis) -> ValidationCheck:
    required_columns = {"department", "amount_2024", "amount_2025", "increase", "yoy_growth"}
    contribution_columns = {"expense_type", "amount_2024", "amount_2025", "increase", "contribution_rate"}
    missing_department = sorted(required_columns - set(analysis.department_yoy.columns))
    missing_contribution = sorted(contribution_columns - set(analysis.contribution_by_type.columns))
    has_invalid_rate = bool(
        analysis.contribution_by_type["contribution_rate"].apply(lambda value: not math.isfinite(float(value))).any()
    )
    passed = not missing_department and not missing_contribution and not has_invalid_rate
    message = "图表数据字段和单位口径完整。" if passed else "图表数据缺少必要字段或存在非法数值。"
    return ValidationCheck(
        check_id="chart_consistency",
        name="图表与数据一致性校验",
        passed=passed,
        severity="error" if not passed else "info",
        message=message,
        details={
            "missing_department_columns": ",".join(missing_department),
            "missing_contribution_columns": ",".join(missing_contribution),
            "has_invalid_rate": has_invalid_rate,
        },
    )


def validate_language_safety(result: AnalysisResult) -> ValidationCheck:
    text = result.summary + "\n" + "\n".join(claim.text for claim in result.claims)
    found = [word for word in FORBIDDEN_CAUSAL_WORDS if word in text]
    return ValidationCheck(
        check_id="language_safety",
        name="因果表达限制校验",
        passed=not found,
        severity="warning" if found else "info",
        message="未发现无证据因果表达。" if not found else f"发现需谨慎使用的因果词：{', '.join(found)}",
        details={"forbidden_words": ",".join(found)},
    )
