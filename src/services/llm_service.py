from __future__ import annotations

import json
import os
from typing import Protocol

from src.models.intent import AnalysisIntent
from src.models.plan import AnalysisPlan, PlanStep
from src.tools.data_profiler import DataProfile


class IntentParser(Protocol):
    def parse(self, question: str, profile: DataProfile) -> AnalysisIntent:
        ...


class RuleBasedIntentParser:
    """Stable local baseline used by the Demo and batch evaluation."""

    model_name = "rule_based"

    def parse(self, question: str, profile: DataProfile) -> AnalysisIntent:
        return parse_user_intent(question, profile)


class OpenAIIntentParser:
    """Optional adapter; it is only instantiated when a real API is configured."""

    model_name = "openai"

    def __init__(self, client=None, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("使用真实模型前请安装可选依赖：pip install -r requirements-llm.txt") from exc
            client = OpenAI()
        self.client = client

    def parse(self, question: str, profile: DataProfile) -> AnalysisIntent:
        fields = [column.name for column in profile.columns]
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是数据分析意图解析器。只输出 JSON，字段包括 task_type、objective、metrics、"
                        "dimensions、filters、time_range、operations、visualizations、"
                        "clarification_needed、clarification_question、confidence。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "available_fields": fields},
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return AnalysisIntent.model_validate(json.loads(content))


def parse_user_intent(question: str, profile: DataProfile) -> AnalysisIntent:
    fields = {column.name for column in profile.columns}
    normalized = question.strip() or "分析 2025 年各部门费用变化，找出同比增长最快的部门，并判断主要增长来自哪些费用类型。"
    unknown_field_terms = {
        "客户": "customer",
        "行业": "industry",
        "客户行业": "customer_industry",
        "预算": "budget",
        "预算金额": "budget_amount",
        "供应商": "vendor",
        "供应商名称": "vendor_name",
        "合同": "contract",
        "合同编号": "contract_id",
    }
    mentioned_missing = [
        label
        for label, canonical in unknown_field_terms.items()
        if label in normalized and canonical not in fields and label not in fields
    ]
    if mentioned_missing:
        return AnalysisIntent(
            task_type="clarification",
            objective="需要确认不存在字段",
            clarification_needed=True,
            clarification_question=f"问题中提到的数据字段不存在：{', '.join(mentioned_missing)}。请确认是否需要改用现有字段，或上传包含这些字段的数据。",
            confidence=0.25,
        )

    required = {"date", "department", "expense_type", "amount"}
    missing = sorted(required - fields)
    if missing:
        return AnalysisIntent(
            task_type="clarification",
            objective="无法执行费用同比分析",
            clarification_needed=True,
            clarification_question=f"当前数据缺少字段：{', '.join(missing)}。请上传包含这些字段的数据，或手动映射字段。",
            confidence=0.2,
        )

    asks_anomaly = any(keyword in normalized for keyword in ["异常", "大额", "极端", "离群"])
    asks_summary = any(keyword in normalized for keyword in ["总费用", "总额", "各部门费用", "是多少", "汇总", "花了多少钱"])
    asks_trend = any(keyword in normalized for keyword in ["趋势", "月度", "月份", "哪几个月"])
    asks_yoy = any(keyword in normalized for keyword in ["同比", "增长", "变化", "最快"]) or asks_trend
    asks_department = any(keyword in normalized for keyword in ["部门", "department"])
    asks_expense_type = any(keyword in normalized for keyword in ["费用类型", "类型", "原因", "来自", "expense_type"])

    if asks_anomaly:
        return AnalysisIntent(
            task_type="anomaly_detection",
            objective="识别异常大额费用记录，并展示异常判断依据",
            metrics=["amount"],
            dimensions=["department", "expense_type"],
            filters={},
            time_range=[],
            operations=["clean", "iqr_anomaly_detection", "rank"],
            visualizations=["scatter_chart", "table"],
            clarification_needed=False,
            clarification_question=None,
            confidence=0.84,
        )

    if asks_summary and not asks_yoy:
        return AnalysisIntent(
            task_type="department_summary",
            objective="统计各部门费用总额并排序",
            metrics=["amount"],
            dimensions=["department"],
            filters={},
            time_range=[],
            operations=["clean", "groupby", "sum", "rank"],
            visualizations=["bar_chart", "table"],
            clarification_needed=False,
            clarification_question=None,
            confidence=0.82,
        )

    if not asks_yoy:
        return AnalysisIntent(
            task_type="clarification",
            objective="需要澄清分析目标",
            metrics=["amount"],
            clarification_needed=True,
            clarification_question="当前版本优先支持 2024/2025 部门费用同比分析。请确认是否按该口径分析。",
            confidence=0.45,
        )

    dimensions = ["department"]
    if asks_expense_type:
        dimensions.append("expense_type")
    if not asks_department:
        dimensions = ["department", "expense_type"]

    return AnalysisIntent(
        task_type="department_yoy",
        objective="分析 2025 年各部门费用同比变化，并下钻增长最快部门的费用类型贡献",
        metrics=["amount"],
        dimensions=dimensions,
        filters={},
        time_range=["2024", "2025"],
        operations=["clean", "groupby", "sum", "year_over_year", "rank", "contribution"],
        visualizations=["bar_chart", "contribution_chart", "line_chart"],
        clarification_needed=False,
        clarification_question=None,
        confidence=0.86,
    )


def generate_analysis_plan(intent: AnalysisIntent) -> AnalysisPlan:
    warnings = []
    if intent.clarification_needed and intent.clarification_question:
        warnings.append(intent.clarification_question)

    if intent.task_type == "department_summary":
        steps = [
            PlanStep(step_id="step_1", action="clean_amount", tool="python", description="清洗 amount 字段并转换为数值。", inputs=["amount"], expected_output="amount_clean"),
            PlanStep(step_id="step_2", action="group_department_total", tool="python", description="按 department 聚合费用总额并排序。", inputs=["department", "amount_clean"], expected_output="department_total_table"),
            PlanStep(step_id="step_3", action="generate_charts", tool="python_plotly", description="生成各部门费用总额柱状图。", inputs=["department_total_table"], expected_output="charts"),
            PlanStep(step_id="step_4", action="validate_result", tool="rules", description="校验部门合计与总费用一致，并检查结论数字。", inputs=["department_total_table", "claims"], expected_output="validation_report"),
            PlanStep(step_id="step_5", action="explain_result", tool="llm_template", description="只基于 Python 计算结果生成结论。", inputs=["calculated_tables"], expected_output="summary_and_claims"),
        ]
    elif intent.task_type == "anomaly_detection":
        steps = [
            PlanStep(step_id="step_1", action="clean_amount", tool="python", description="清洗 amount 字段并转换为数值。", inputs=["amount"], expected_output="amount_clean"),
            PlanStep(step_id="step_2", action="detect_amount_anomalies", tool="python", description="使用 IQR 方法识别异常大额费用。", inputs=["amount_clean"], expected_output="anomaly_table"),
            PlanStep(step_id="step_3", action="rank_anomalies", tool="python", description="按金额降序展示异常记录及判断阈值。", inputs=["anomaly_table"], expected_output="ranked_anomalies"),
            PlanStep(step_id="step_4", action="generate_charts", tool="python_plotly", description="生成异常值分布图。", inputs=["amount_clean", "anomaly_flag"], expected_output="charts"),
            PlanStep(step_id="step_5", action="validate_result", tool="rules", description="校验异常记录均超过阈值，并检查最大异常金额。", inputs=["anomaly_table", "claims"], expected_output="validation_report"),
            PlanStep(step_id="step_6", action="explain_result", tool="llm_template", description="只基于 Python 计算结果生成结论。", inputs=["calculated_tables"], expected_output="summary_and_claims"),
        ]
    else:
        steps = [
            PlanStep(
                step_id="step_1",
                action="clean_amount",
                tool="python",
                description="清洗 amount 字段，去除货币符号、千分位逗号和空格，并转换为数值。",
                inputs=["amount"],
                expected_output="amount_clean",
            ),
            PlanStep(
                step_id="step_2",
                action="clean_date",
                tool="python",
                description="解析 date 字段，生成 year 和 month，用于同比和趋势分析。",
                inputs=["date"],
                expected_output="date_clean, year, month",
            ),
            PlanStep(
                step_id="step_3",
                action="group_department_yoy",
                tool="python",
                description="按 department 和 year 聚合 amount_clean，计算 2025 相比 2024 的同比增长率。",
                inputs=["department", "year", "amount_clean"],
                expected_output="department_yoy_table",
            ),
            PlanStep(
                step_id="step_4",
                action="rank_top_department",
                tool="python",
                description="根据同比增长率和新增费用排序，找出增长最快部门。",
                inputs=["department_yoy_table"],
                expected_output="top_department",
            ),
            PlanStep(
                step_id="step_5",
                action="drilldown_expense_type",
                tool="python",
                description="对增长最快部门按 expense_type 下钻，计算新增费用贡献。",
                inputs=["top_department", "expense_type", "amount_clean"],
                expected_output="expense_type_contribution_table",
            ),
            PlanStep(
                step_id="step_6",
                action="generate_charts",
                tool="python_plotly",
                description="生成部门同比柱状图、费用类型贡献图和月度趋势图。",
                inputs=["department_yoy_table", "expense_type_contribution_table", "monthly_trend_table"],
                expected_output="charts",
            ),
            PlanStep(
                step_id="step_7",
                action="validate_result",
                tool="rules",
                description="校验字段合法性、数值一致性、排名、文字数字一致性和图表数据口径。",
                inputs=["calculated_tables", "claims", "charts"],
                expected_output="validation_report",
            ),
            PlanStep(
                step_id="step_8",
                action="explain_result",
                tool="llm_template",
                description="只基于 Python 结构化结果生成自然语言结论，不额外创造数字。",
                inputs=["calculated_tables"],
                expected_output="summary_and_claims",
            ),
        ]

    return AnalysisPlan(
        objective=intent.objective,
        warnings=warnings,
        steps=steps,
    )
