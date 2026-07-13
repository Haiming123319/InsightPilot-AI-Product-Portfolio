from __future__ import annotations

import pandas as pd

from src.models.config import CleaningConfig
from src.models.intent import AnalysisIntent
from src.models.plan import AnalysisPlan
from src.models.result import AnalysisClaim, AnalysisResult, Evidence
from src.models.validation import ValidationCheck
from src.models.validation import ValidationReport
from src.services.observability import ExecutionLogger
from src.services.plan_service import validate_analysis_plan
from src.tools.analysis_tools import (
    AnomalyAnalysis,
    DepartmentSummaryAnalysis,
    DepartmentYoyAnalysis,
    run_anomaly_analysis,
    run_department_summary_analysis,
    run_department_yoy_analysis,
)
from src.tools.validation_tools import validate_analysis_result


ANALYSIS_CODE = """cleaned = clean_expense_dataframe(df)
valid = cleaned.dropna(subset=["date_clean", "amount_clean", "department", "expense_type"])
valid = valid[valid["year"].isin([2024, 2025])]
yearly = valid.groupby(["department", "year"], as_index=False)["amount_clean"].sum()
pivot = yearly.pivot(index="department", columns="year", values="amount_clean").fillna(0)
yoy_growth = (amount_2025 - amount_2024) / amount_2024
top_department = department_yoy.sort_values(["yoy_growth", "increase"], ascending=False).iloc[0]
contribution = top_department_rows.groupby(["expense_type", "year"])["amount_clean"].sum()
"""

SUMMARY_CODE = """cleaned = clean_expense_dataframe(df)
valid = cleaned.dropna(subset=["department", "amount_clean"])
department_totals = valid.groupby("department", as_index=False)["amount_clean"].sum()
department_totals["share"] = department_totals["total_amount"] / total_amount
"""

ANOMALY_CODE = """cleaned = clean_expense_dataframe(df)
valid = cleaned.dropna(subset=["amount_clean"])
q1 = valid["amount_clean"].quantile(0.25)
q3 = valid["amount_clean"].quantile(0.75)
iqr = q3 - q1
threshold = q3 + 1.5 * iqr
anomalies = valid[valid["amount_clean"] > threshold]
"""


def execute_analysis_task(
    df,
    intent: AnalysisIntent,
    plan: AnalysisPlan | None = None,
    cleaning_config: CleaningConfig | None = None,
    event_logger: ExecutionLogger | None = None,
):
    logger = event_logger or ExecutionLogger()
    config = cleaning_config or CleaningConfig()
    logger.log("task_started", details={"task_type": intent.task_type, "row_count": int(len(df))})
    logger.log("intent_parsed", details={"confidence": intent.confidence, "task_type": intent.task_type})

    try:
        if plan is not None:
            plan_errors = validate_analysis_plan(plan, intent)
            if plan_errors:
                raise AnalysisExecutionError("分析计划无法执行：" + "；".join(plan_errors))
            logger.log(
                "plan_generated",
                details={"step_count": len(plan.steps), "enabled_steps": sum(step.enabled for step in plan.steps)},
            )
        else:
            logger.log("plan_generated", details={"step_count": 0, "source": "default_execution"})

        logger.log(
            "tool_started",
            component="python_executor",
            details={
                "task_type": intent.task_type,
                "cleaning_config": config.model_dump(),
            },
        )
        if intent.task_type == "department_summary":
            output = execute_department_summary_task(df, cleaning_config=config)
        elif intent.task_type == "anomaly_detection":
            output = execute_anomaly_task(df, cleaning_config=config)
        else:
            output = execute_department_yoy_task(df, cleaning_config=config)
        logger.log("tool_finished", component="python_executor", details={"task_type": intent.task_type})
        logger.log("validation_finished", component="validation", details={"passed": output[2].passed})
        logger.log("task_finished", details={"validation_passed": output[2].passed})
        return output
    except Exception as exc:
        logger.log("task_failed", status="failed", details={"error_type": type(exc).__name__, "message": str(exc)})
        raise


def execute_department_yoy_task(
    df,
    cleaning_config: CleaningConfig | None = None,
) -> tuple[DepartmentYoyAnalysis, AnalysisResult, ValidationReport]:
    config = cleaning_config or CleaningConfig()
    analysis = run_department_yoy_analysis(df, cleaning_config=config)
    result = build_result(analysis, config)
    validation_report = validate_analysis_result(df, analysis, result)
    return analysis, result, validation_report


def execute_department_summary_task(
    df,
    cleaning_config: CleaningConfig | None = None,
) -> tuple[DepartmentSummaryAnalysis, AnalysisResult, ValidationReport]:
    config = cleaning_config or CleaningConfig()
    analysis = run_department_summary_analysis(df, cleaning_config=config)
    result = build_summary_result(analysis, config)
    validation_report = _validate_summary_result(analysis, result)
    return analysis, result, validation_report


def execute_anomaly_task(
    df,
    cleaning_config: CleaningConfig | None = None,
) -> tuple[AnomalyAnalysis, AnalysisResult, ValidationReport]:
    config = cleaning_config or CleaningConfig()
    analysis = run_anomaly_analysis(df, cleaning_config=config)
    result = build_anomaly_result(analysis, config)
    validation_report = _validate_anomaly_result(analysis, result)
    return analysis, result, validation_report


def build_result(analysis: DepartmentYoyAnalysis, cleaning_config: CleaningConfig | None = None) -> AnalysisResult:
    top_row = analysis.department_yoy.iloc[0]
    top_department = str(top_row["department"])
    top_growth = top_row["yoy_growth"]
    top_growth_text = "新增费用" if top_growth is None or pd.isna(top_growth) else f"{float(top_growth) * 100:.1f}%"

    contribution_top = analysis.contribution_by_type.head(2)
    contribution_text = "、".join(
        f"{row.expense_type}（新增 {row.increase:,.0f}，贡献 {row.contribution_rate * 100:.1f}%）"
        for row in contribution_top.itertuples()
    )

    total_yoy_text = "无法计算" if analysis.yoy_growth is None else f"{analysis.yoy_growth * 100:.1f}%"
    summary = (
        f"2025 年总费用为 {analysis.total_2025:,.0f}，整体同比为 {total_yoy_text}。"
        f"{top_department} 是当前口径下增长最快的部门，增长主要集中在 {contribution_text}。"
    )

    claims = [
        AnalysisClaim(
            text=f"{top_department} 在部门同比排名中位列第 1，增长率为 {top_growth_text}。",
            entity=top_department,
            metric="yoy_growth",
            value="新增" if top_growth is None or pd.isna(top_growth) else round(float(top_growth) * 100, 2),
            unit="" if top_growth is None or pd.isna(top_growth) else "%",
            evidence_id="table_department_yoy",
        ),
        AnalysisClaim(
            text=f"2025 年总费用为 {analysis.total_2025:,.0f}。",
            entity="全部部门",
            metric="amount_2025",
            value=round(analysis.total_2025, 2),
            unit="元",
            evidence_id="table_department_yoy",
        ),
    ]

    if not contribution_top.empty:
        first = contribution_top.iloc[0]
        claims.append(
            AnalysisClaim(
                text=f"{top_department} 新增费用中，{first['expense_type']} 贡献最高，贡献率为 {first['contribution_rate'] * 100:.1f}%。",
                entity=str(first["expense_type"]),
                metric="contribution_rate",
                value=round(float(first["contribution_rate"]) * 100, 2),
                unit="%",
                evidence_id="table_expense_type_contribution",
            )
        )

    limitations = []
    if analysis.excluded_rows:
        limitations.append(f"有 {analysis.excluded_rows} 行因日期、金额或关键维度缺失未纳入 2024/2025 同比计算。")
    limitations.append("本分析是描述性分析，只能说明增长集中在哪些费用类型，不能证明因果关系。")
    limitations.extend(_cleaning_limitations(cleaning_config))

    evidence = [
        Evidence(
            evidence_id="table_department_yoy",
            fields=["date", "department", "amount"],
            formula="同比增长率 = (2025 年费用 - 2024 年费用) / 2024 年费用；2024 年为 0 时不输出百分比。",
            row_count=analysis.covered_rows,
            code=ANALYSIS_CODE,
        ),
        Evidence(
            evidence_id="table_expense_type_contribution",
            fields=["department", "expense_type", "amount"],
            formula="贡献率 = 某费用类型新增费用 / 增长最快部门总新增费用。",
            row_count=analysis.covered_rows,
            code=ANALYSIS_CODE,
        ),
    ]

    return AnalysisResult(summary=summary, claims=claims, limitations=limitations, evidence=evidence)


def build_summary_result(analysis: DepartmentSummaryAnalysis, cleaning_config: CleaningConfig | None = None) -> AnalysisResult:
    top_row = analysis.department_totals.iloc[0]
    summary = (
        f"本次可计算费用总额为 {analysis.total_amount:,.0f}。"
        f"{analysis.top_department} 费用最高，为 {top_row['total_amount']:,.0f}，占比 {top_row['share'] * 100:.1f}%。"
    )
    claims = [
        AnalysisClaim(
            text=f"{analysis.top_department} 是费用最高的部门，费用总额为 {top_row['total_amount']:,.0f}。",
            entity=analysis.top_department,
            metric="department_total",
            value=round(float(top_row["total_amount"]), 2),
            unit="元",
            evidence_id="table_department_totals",
        ),
        AnalysisClaim(
            text=f"全部部门费用总额为 {analysis.total_amount:,.0f}。",
            entity="全部部门",
            metric="total_amount",
            value=round(analysis.total_amount, 2),
            unit="元",
            evidence_id="table_department_totals",
        ),
    ]
    limitations = []
    if analysis.excluded_rows:
        limitations.append(f"有 {analysis.excluded_rows} 行因部门或金额缺失未纳入汇总。")
    limitations.extend(_cleaning_limitations(cleaning_config))
    evidence = [
        Evidence(
            evidence_id="table_department_totals",
            fields=["department", "amount"],
            formula="部门费用总额 = 按 department 分组后对 amount_clean 求和；占比 = 部门费用 / 全部部门费用。",
            row_count=analysis.covered_rows,
            code=SUMMARY_CODE,
        )
    ]
    return AnalysisResult(summary=summary, claims=claims, limitations=limitations, evidence=evidence)


def build_anomaly_result(analysis: AnomalyAnalysis, cleaning_config: CleaningConfig | None = None) -> AnalysisResult:
    if analysis.anomaly_table.empty:
        summary = f"基于 IQR 方法未发现超过 {analysis.threshold:,.0f} 的异常大额费用。"
        claims = [
            AnalysisClaim(
                text="当前数据未发现异常大额费用。",
                entity="全部记录",
                metric="anomaly_count",
                value=0,
                unit="条",
                evidence_id="table_amount_anomalies",
            )
        ]
    else:
        top = analysis.anomaly_table.iloc[0]
        summary = (
            f"基于 IQR 方法识别出 {analysis.anomaly_count} 条异常大额费用。"
            f"最大异常金额为 {analysis.max_anomaly_amount:,.0f}，阈值为 {analysis.threshold:,.0f}。"
        )
        claims = [
            AnalysisClaim(
                text=f"共发现 {analysis.anomaly_count} 条异常大额费用。",
                entity="全部记录",
                metric="anomaly_count",
                value=analysis.anomaly_count,
                unit="条",
                evidence_id="table_amount_anomalies",
            ),
            AnalysisClaim(
                text=f"最大异常金额为 {analysis.max_anomaly_amount:,.0f}，来自 {top.get('department', '未知部门')}。",
                entity=str(top.get("department", "未知部门")),
                metric="max_anomaly_amount",
                value=round(analysis.max_anomaly_amount, 2),
                unit="元",
                evidence_id="table_amount_anomalies",
            ),
        ]
    limitations = ["异常判断采用 IQR 统计阈值，只代表金额分布异常，不等于业务违规。"]
    limitations.extend(_cleaning_limitations(cleaning_config))
    evidence = [
        Evidence(
            evidence_id="table_amount_anomalies",
            fields=["amount", "department", "expense_type", "date"],
            formula="异常阈值 = Q3 + 1.5 * IQR；amount_clean 大于该阈值时标记为异常大额费用。",
            row_count=analysis.covered_rows,
            code=ANOMALY_CODE,
        )
    ]
    return AnalysisResult(summary=summary, claims=claims, limitations=limitations, evidence=evidence)


def _validate_summary_result(analysis: DepartmentSummaryAnalysis, result: AnalysisResult) -> ValidationReport:
    department_sum = float(analysis.department_totals["total_amount"].sum())
    diff = abs(department_sum - analysis.total_amount)
    checks = [
        ValidationCheck(
            check_id="summary_numeric_consistency",
            name="汇总数值一致性校验",
            passed=diff <= 0.01,
            severity="error" if diff > 0.01 else "info",
            message="部门费用合计与总费用一致。" if diff <= 0.01 else "部门费用合计与总费用不一致。",
            details={"department_sum": round(department_sum, 2), "total_amount": round(analysis.total_amount, 2)},
        ),
        ValidationCheck(
            check_id="summary_claim_consistency",
            name="汇总结论一致性校验",
            passed=any(claim.entity == analysis.top_department for claim in result.claims),
            severity="error",
            message="结论引用了费用最高部门。" if any(claim.entity == analysis.top_department for claim in result.claims) else "结论未引用费用最高部门。",
            details={"top_department": analysis.top_department},
        ),
    ]
    return ValidationReport(passed=all(check.passed for check in checks), checks=checks)


def _cleaning_limitations(cleaning_config: CleaningConfig | None) -> list[str]:
    config = cleaning_config or CleaningConfig()
    limitations: list[str] = []
    if config.anomaly_action == "exclude":
        limitations.append("本次重算已按 IQR 阈值排除异常大额费用记录。")
    if config.missing_amount == "zero":
        limitations.append("缺失或无法转换的金额已按 0 纳入计算。")
    if config.duplicate_rows == "keep_all":
        limitations.append("本次计算保留了重复记录，请结合业务主键复核。")
    return limitations


def _validate_anomaly_result(analysis: AnomalyAnalysis, result: AnalysisResult) -> ValidationReport:
    all_above_threshold = (
        bool((analysis.anomaly_table["amount_clean"] > analysis.threshold).all()) if not analysis.anomaly_table.empty else True
    )
    claim_count_ok = any(claim.metric == "anomaly_count" and int(claim.value) == analysis.anomaly_count for claim in result.claims)
    checks = [
        ValidationCheck(
            check_id="anomaly_threshold_consistency",
            name="异常阈值一致性校验",
            passed=all_above_threshold,
            severity="error" if not all_above_threshold else "info",
            message="所有异常记录均超过 IQR 阈值。" if all_above_threshold else "存在未超过阈值的异常记录。",
            details={"threshold": round(analysis.threshold, 2), "anomaly_count": analysis.anomaly_count},
        ),
        ValidationCheck(
            check_id="anomaly_claim_consistency",
            name="异常结论一致性校验",
            passed=claim_count_ok,
            severity="error" if not claim_count_ok else "info",
            message="异常数量结论与明细表一致。" if claim_count_ok else "异常数量结论与明细表不一致。",
            details={"anomaly_count": analysis.anomaly_count},
        ),
    ]
    return ValidationReport(passed=all(check.passed for check in checks), checks=checks)
