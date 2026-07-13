from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    check_id: str
    name: str
    passed: bool
    severity: str = "info"
    message: str
    details: dict[str, float | int | str | bool] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    passed: bool
    checks: list[ValidationCheck]

    @property
    def failed_checks(self) -> list[ValidationCheck]:
        return [check for check in self.checks if not check.passed]

