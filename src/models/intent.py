from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalysisIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = "department_yoy"
    objective: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    visualizations: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class ParserMetadata(BaseModel):
    """Metadata used to compare parser choices as product experiments."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    request_id: str | None = None
    validation_errors: list[str] = Field(default_factory=list)


class IntentParseResult(BaseModel):
    """Stable boundary object returned by every parser route."""

    model_config = ConfigDict(extra="forbid")

    intent: AnalysisIntent
    metadata: ParserMetadata
