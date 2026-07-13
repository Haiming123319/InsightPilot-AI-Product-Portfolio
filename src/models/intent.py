from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisIntent(BaseModel):
    task_type: str = "department_yoy"
    objective: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    time_range: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    visualizations: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)
