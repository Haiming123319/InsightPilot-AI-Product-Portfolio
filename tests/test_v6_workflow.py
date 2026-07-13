from __future__ import annotations

import pandas as pd

from src.models.config import CleaningConfig
from src.services.followup_service import apply_followup
from src.services.llm_service import OpenAIIntentParser
from src.services.observability import ExecutionLogger
from src.services.plan_service import validate_analysis_plan
from src.services.task_service import execute_analysis_task
from src.tools.data_mapping import apply_field_mapping, suggest_field_mapping
from src.services.llm_service import generate_analysis_plan, parse_user_intent
from src.tools.data_profiler import profile_dataframe


def test_field_mapping_renames_business_columns_to_standard_fields() -> None:
    df = pd.DataFrame(
        {
            "发生日期": ["2024-01-01"],
            "成本中心": ["市场部"],
            "费用科目": ["差旅费"],
            "含税金额": [100],
        }
    )

    mapping = suggest_field_mapping(df)
    mapped = apply_field_mapping(df, mapping)

    assert {"date", "department", "expense_type", "amount"}.issubset(mapped.columns)


def test_followup_changes_cleaning_config() -> None:
    result = apply_followup("排除异常值后重新分析", CleaningConfig())

    assert result.supported is True
    assert result.cleaning_config.anomaly_action == "exclude"


def test_plan_validation_blocks_disabling_required_step() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2025-01-01"],
            "department": ["市场部", "市场部"],
            "expense_type": ["差旅费", "差旅费"],
            "amount": [100, 120],
        }
    )
    intent = parse_user_intent("分析部门费用同比变化", profile_dataframe(df))
    plan = generate_analysis_plan(intent)
    plan.steps[2].enabled = False

    errors = validate_analysis_plan(plan, intent)

    assert any("group_department_yoy" in error for error in errors)


def test_execution_logger_records_v6_events() -> None:
    df = pd.DataFrame(
        [
            {"date": "2024-01-01", "department": "市场部", "expense_type": "差旅费", "amount": 100},
            {"date": "2025-01-01", "department": "市场部", "expense_type": "差旅费", "amount": 120},
        ]
    )
    intent = parse_user_intent("分析部门费用同比变化", profile_dataframe(df))
    plan = generate_analysis_plan(intent)
    logger = ExecutionLogger()

    _, _, report = execute_analysis_task(df, intent, plan=plan, event_logger=logger)

    event_types = [event["event_type"] for event in logger.events]
    assert report.passed is True
    assert event_types[0] == "task_started"
    assert "validation_finished" in event_types
    assert event_types[-1] == "task_finished"


def test_openai_adapter_accepts_structured_json_from_injected_client() -> None:
    class Message:
        content = '{"task_type":"department_summary","objective":"统计部门费用","confidence":0.9}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class Completions:
        def create(self, **kwargs):
            return Response()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    df = pd.DataFrame({"department": ["市场部"], "amount": [100]})
    parser = OpenAIIntentParser(client=Client(), model="test-model")
    intent = parser.parse("各部门总费用", profile_dataframe(df))

    assert intent.task_type == "department_summary"
    assert intent.confidence == 0.9
