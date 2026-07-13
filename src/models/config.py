from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CANONICAL_FIELDS = ("date", "department", "expense_type", "amount")


class FieldMapping(BaseModel):
    mapping: dict[str, str | None] = Field(default_factory=dict)

    def selected_columns(self) -> list[str]:
        return [column for column in self.mapping.values() if column]


class CleaningConfig(BaseModel):
    missing_amount: Literal["exclude", "zero", "error"] = "exclude"
    duplicate_rows: Literal["remove", "keep_first", "keep_last", "keep_all"] = "remove"
    anomaly_action: Literal["include", "exclude"] = "include"
    normalize_text: bool = True
