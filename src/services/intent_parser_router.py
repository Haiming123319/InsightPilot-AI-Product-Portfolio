from __future__ import annotations

import csv
import os
import time
import uuid
from pathlib import Path

from src.models.intent import IntentParseResult, ParserMetadata
from src.services.intent_validation import validate_analysis_intent
from src.services.llm_service import OpenAIIntentParser, RuleBasedIntentParser
from src.tools.data_profiler import DataProfile


SUPPORTED_PROVIDERS = {"rule_based", "openai", "openai_with_fallback"}


class IntentParserError(RuntimeError):
    def __init__(self, message: str, *, provider: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause


def parse_intent(
    question: str,
    profile: DataProfile,
    provider: str | None = None,
    *,
    parser=None,
    fallback_parser=None,
    fallback_log_path: str | Path | None = None,
) -> IntentParseResult:
    """Route intent parsing while keeping execution outside the model boundary."""

    selected_provider = provider or os.getenv("LLM_PROVIDER", "rule_based")
    if selected_provider not in SUPPORTED_PROVIDERS:
        raise IntentParserError(
            f"不支持的解析模式：{selected_provider}。",
            provider=selected_provider,
        )

    fallback_enabled = os.getenv("ENABLE_LLM_FALLBACK", "true").strip().lower() not in {"0", "false", "no"}

    if selected_provider == "rule_based":
        started = time.perf_counter()
        intent = (parser or RuleBasedIntentParser()).parse(question, profile)
        return _build_result(
            intent,
            provider="rule_based",
            model="rule_based",
            latency_ms=(time.perf_counter() - started) * 1000,
            profile=profile,
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if parser is None and not api_key:
        error = RuntimeError("未配置 OPENAI_API_KEY。")
        if selected_provider == "openai_with_fallback" and fallback_enabled:
            return _fallback(
                question,
                profile,
                selected_provider,
                reason=str(error),
                fallback_parser=fallback_parser,
                fallback_log_path=fallback_log_path,
            )
        raise IntentParserError(
            "当前选择了 OpenAI 模式，但未配置 OPENAI_API_KEY。请切换规则基线或补充环境变量。",
            provider=selected_provider,
            cause=error,
        )

    model_parser = parser or OpenAIIntentParser(api_key=api_key)
    started = time.perf_counter()
    try:
        intent = model_parser.parse(question, profile)
        call_metadata = getattr(model_parser, "last_call_metadata", {})
        return _build_result(
            intent,
            provider="openai",
            model=getattr(model_parser, "model", None),
            latency_ms=call_metadata.get("latency_ms") or (time.perf_counter() - started) * 1000,
            input_tokens=call_metadata.get("input_tokens"),
            output_tokens=call_metadata.get("output_tokens"),
            total_tokens=call_metadata.get("total_tokens"),
            request_id=call_metadata.get("request_id"),
            profile=profile,
        )
    except Exception as exc:
        if selected_provider != "openai_with_fallback" or not fallback_enabled:
            raise IntentParserError(
                _friendly_openai_error(exc),
                provider=selected_provider,
                cause=exc,
            ) from exc
        return _fallback(
            question,
            profile,
            selected_provider,
            reason=_friendly_openai_error(exc),
            fallback_parser=fallback_parser,
            fallback_log_path=fallback_log_path,
        )


def _fallback(
    question: str,
    profile: DataProfile,
    requested_provider: str,
    *,
    reason: str,
    fallback_parser=None,
    fallback_log_path: str | Path | None = None,
) -> IntentParseResult:
    parser = fallback_parser or RuleBasedIntentParser()
    started = time.perf_counter()
    intent = parser.parse(question, profile)
    result = _build_result(
        intent,
        provider="rule_based",
        model="rule_based",
        latency_ms=(time.perf_counter() - started) * 1000,
        fallback_used=True,
        fallback_reason=reason,
        profile=profile,
    )
    if fallback_log_path:
        _append_fallback_log(fallback_log_path, question, requested_provider, reason)
    return result


def _build_result(
    intent,
    *,
    provider: str,
    model: str | None,
    latency_ms: float,
    profile: DataProfile,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    request_id: str | None = None,
) -> IntentParseResult:
    errors = validate_analysis_intent(intent, profile)
    if errors:
        intent = intent.model_copy(
            update={
                "task_type": "clarification",
                "objective": "需要确认字段或分析口径",
                "clarification_needed": True,
                "clarification_question": "；".join(errors) + " 请确认后再继续。",
                "confidence": min(intent.confidence, 0.3),
            }
        )
    return IntentParseResult(
        intent=intent,
        metadata=ParserMetadata(
            provider=provider,
            model=model,
            latency_ms=round(latency_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            request_id=request_id or f"local_{uuid.uuid4().hex[:10]}",
            validation_errors=errors,
        ),
    )


def _friendly_openai_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).strip() or "模型调用失败。"
    if "timeout" in name or "timeout" in message.lower():
        return "OpenAI 调用超时，请检查网络或切换规则基线。"
    if "rate" in name or "429" in message:
        return "OpenAI 请求受到限流，请稍后重试或切换规则基线。"
    if "auth" in name or "401" in message or "api key" in message.lower():
        return "OpenAI 鉴权失败，请检查 OPENAI_API_KEY。"
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "模型返回的结构化意图无法通过格式校验。"
    return f"OpenAI 调用失败：{message[:160]}"


def _append_fallback_log(path: str | Path, question: str, provider: str, reason: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["case_id", "category", "question", "failure_reason", "improvement"]
    needs_header = not output.exists() or output.stat().st_size == 0
    with output.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if needs_header:
            writer.writeheader()
        writer.writerow(
            {
                "case_id": f"LLM-FALLBACK-{uuid.uuid4().hex[:8]}",
                "category": "LLM 回退",
                "question": question,
                "failure_reason": f"{provider}: {reason}",
                "improvement": "记录模型失败原因，比较回退后的任务完成率与体验成本。",
            }
        )
