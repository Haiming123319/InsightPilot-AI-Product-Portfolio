from __future__ import annotations

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step_id: str
    action: str
    tool: str
    description: str
    inputs: list[str] = Field(default_factory=list)
    expected_output: str
    enabled: bool = True
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    objective: str
    steps: list[PlanStep]
    warnings: list[str] = Field(default_factory=list)
