from __future__ import annotations

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    evidence_id: str
    fields: list[str]
    formula: str
    row_count: int
    code: str


class AnalysisClaim(BaseModel):
    text: str
    entity: str
    metric: str
    value: float | str
    unit: str
    evidence_id: str


class AnalysisResult(BaseModel):
    summary: str
    claims: list[AnalysisClaim]
    limitations: list[str] = Field(default_factory=list)
    evidence: list[Evidence]

