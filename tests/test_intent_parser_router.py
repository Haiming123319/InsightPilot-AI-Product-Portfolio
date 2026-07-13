from __future__ import annotations

import json

import pandas as pd
import pytest

from src.models.intent import AnalysisIntent
from src.services.intent_parser_router import IntentParserError, parse_intent
from src.services.llm_service import OpenAIIntentParser
from src.tools.data_profiler import profile_dataframe, profile_to_llm_payload


def _profile():
    return profile_dataframe(
        pd.DataFrame(
            {
                "date": ["2024-01-01", "2025-01-01"],
                "department": ["市场部", "市场部"],
                "expense_type": ["差旅费", "差旅费"],
                "amount": [100, 120],
            }
        )
    )


def _intent(**updates) -> AnalysisIntent:
    values = {
        "task_type": "department_yoy",
        "objective": "比较部门同比变化",
        "metrics": ["amount"],
        "dimensions": ["department"],
        "operations": ["clean", "groupby", "sum", "year_over_year", "rank"],
        "time_range": ["2024", "2025"],
        "confidence": 0.8,
    }
    values.update(updates)
    return AnalysisIntent(**values)


class FakeParser:
    model = "test-model"

    def __init__(self, intent=None, error: Exception | None = None):
        self.intent = intent or _intent()
        self.error = error
        self.last_call_metadata = {
            "latency_ms": 12.5,
            "input_tokens": 30,
            "output_tokens": 18,
            "total_tokens": 48,
            "request_id": "req_test",
        }

    def parse(self, question, profile):
        if self.error:
            raise self.error
        return self.intent


def test_rule_provider_returns_uniform_result() -> None:
    result = parse_intent("分析部门费用同比变化", _profile(), provider="rule_based")

    assert result.intent.task_type == "department_yoy"
    assert result.metadata.provider == "rule_based"
    assert result.metadata.fallback_used is False


def test_openai_provider_returns_metadata_from_injected_parser() -> None:
    result = parse_intent("比较 2024 和 2025", _profile(), provider="openai", parser=FakeParser())

    assert result.metadata.provider == "openai"
    assert result.metadata.model == "test-model"
    assert result.metadata.total_tokens == 48
    assert result.metadata.request_id == "req_test"


def test_openai_requires_api_key_when_no_parser_is_injected(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(IntentParserError, match="未配置 OPENAI_API_KEY"):
        parse_intent("分析部门费用同比变化", _profile(), provider="openai")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (TimeoutError("timeout"), "超时"),
        (RuntimeError("429 rate limit"), "限流"),
        (RuntimeError("401 api key invalid"), "鉴权失败"),
        (ConnectionError("network down"), "调用失败"),
    ],
)
def test_openai_failures_are_user_readable_without_fallback(error, message) -> None:
    with pytest.raises(IntentParserError, match=message):
        parse_intent("分析部门费用同比变化", _profile(), provider="openai", parser=FakeParser(error=error))


def test_openai_failure_uses_rule_fallback_and_writes_bad_case(tmp_path) -> None:
    log_path = tmp_path / "bad_cases_log.csv"
    result = parse_intent(
        "分析部门费用同比变化",
        _profile(),
        provider="openai_with_fallback",
        parser=FakeParser(error=ConnectionError("network down")),
        fallback_log_path=log_path,
    )

    assert result.metadata.provider == "rule_based"
    assert result.metadata.fallback_used is True
    assert "调用失败" in (result.metadata.fallback_reason or "")
    assert "LLM 回退" in log_path.read_text(encoding="utf-8")


def test_missing_api_key_can_fallback(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = parse_intent("分析部门费用同比变化", _profile(), provider="openai_with_fallback")

    assert result.metadata.fallback_used is True
    assert "OPENAI_API_KEY" in (result.metadata.fallback_reason or "")


def test_model_field_hallucination_is_blocked_before_execution() -> None:
    result = parse_intent(
        "分析预算",
        _profile(),
        provider="openai",
        parser=FakeParser(intent=_intent(metrics=["budget_amount"])),
    )

    assert result.intent.clarification_needed is True
    assert result.intent.task_type == "clarification"
    assert any("不存在字段" in error for error in result.metadata.validation_errors)


def test_continuous_date_range_accepts_middle_year() -> None:
    profile = profile_dataframe(
        pd.DataFrame(
            {
                "date": ["2023-01-01", "2024-01-01", "2025-01-01"],
                "department": ["市场部", "市场部", "市场部"],
                "expense_type": ["差旅费", "差旅费", "差旅费"],
                "amount": [100, 110, 120],
            }
        )
    )
    result = parse_intent("分析 2024 和 2025", profile, provider="openai", parser=FakeParser())

    assert result.intent.clarification_needed is False
    assert result.metadata.validation_errors == []


def test_invalid_model_structure_is_rejected() -> None:
    class Message:
        content = '{"task_type":"department_yoy","objective":"x","unexpected":true}'

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

    parser = OpenAIIntentParser(client=Client(), model="test-model")
    with pytest.raises(ValueError):
        parser.parse("分析部门费用", _profile())


def test_responses_api_uses_strict_pydantic_output_and_no_full_dataframe() -> None:
    class Usage:
        input_tokens = 10
        output_tokens = 8
        total_tokens = 18

    class Response:
        output_parsed = _intent()
        usage = Usage()
        id = "resp_test"

    class Responses:
        def __init__(self):
            self.kwargs = None

        def parse(self, **kwargs):
            self.kwargs = kwargs
            return Response()

    class Client:
        def __init__(self):
            self.responses = Responses()

    client = Client()
    parser = OpenAIIntentParser(client=client, model="test-model")
    result = parse_intent("分析部门费用同比变化", _profile(), provider="openai", parser=parser)
    serialized_input = json.dumps(client.responses.kwargs["input"], ensure_ascii=False)

    assert client.responses.kwargs["text_format"] is AnalysisIntent
    assert result.metadata.total_tokens == 18
    assert "DataFrame" not in serialized_input
    assert "budget_amount" not in serialized_input


def test_profile_payload_limits_and_redacts_text_samples() -> None:
    profile = profile_dataframe(
        pd.DataFrame(
            {
                "date": ["2024-01-01", "2025-01-01"],
                "department": ["市场部", "销售部"],
                "employee_name": ["张三", "李四"],
                "amount": [100, 120],
            }
        )
    )
    payload = profile_to_llm_payload(profile, max_samples=2)
    employee_column = next(column for column in payload["columns"] if column["name"] == "employee_name")

    assert len(employee_column["sample_values"]) <= 2
    assert employee_column["sample_values"] == ["[redacted]", "[redacted]"]
