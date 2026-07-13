from __future__ import annotations

import pandas as pd

from src.services.llm_service import generate_analysis_plan, parse_user_intent
from src.services.task_service import execute_department_yoy_task
from src.tools.data_profiler import profile_dataframe


def test_parse_intent_and_generate_plan() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2025-01-01"],
            "department": ["市场部", "市场部"],
            "expense_type": ["差旅费", "差旅费"],
            "amount": [100, 160],
        }
    )
    profile = profile_dataframe(df)

    intent = parse_user_intent("分析各部门费用同比变化，并找出增长原因", profile)
    plan = generate_analysis_plan(intent)

    assert intent.clarification_needed is False
    assert "department" in intent.dimensions
    assert any(step.action == "group_department_yoy" for step in plan.steps)
    assert any(step.action == "generate_charts" for step in plan.steps)


def test_execute_department_yoy_task() -> None:
    df = pd.DataFrame(
        [
            {"date": "2024-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "100"},
            {"date": "2025-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "180"},
            {"date": "2024-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "200"},
            {"date": "2025-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "220"},
            {"date": "bad-date", "department": "销售部", "expense_type": "广告投放", "amount": "x"},
        ]
    )

    analysis, result, report = execute_department_yoy_task(df)

    assert analysis.top_department == "市场部"
    assert analysis.covered_rows == 4
    assert analysis.excluded_rows == 1
    assert result.claims
    assert result.evidence[0].formula.startswith("同比增长率")
    assert report.passed is True


def test_missing_required_fields_needs_clarification() -> None:
    df = pd.DataFrame({"department": ["市场部"], "amount": [100]})
    profile = profile_dataframe(df)

    intent = parse_user_intent("分析同比", profile)

    assert intent.clarification_needed is True
    assert "缺少字段" in (intent.clarification_question or "")
