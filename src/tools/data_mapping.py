from __future__ import annotations

import pandas as pd

from src.models.config import CANONICAL_FIELDS, FieldMapping


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "日期", "发生日期", "费用日期", "时间"),
    "department": ("department", "部门", "成本中心", "组织", "部门名称"),
    "expense_type": ("expense_type", "费用类型", "费用科目", "科目", "费用类别"),
    "amount": ("amount", "金额", "费用金额", "含税金额", "成本", "费用"),
}


def suggest_field_mapping(df: pd.DataFrame) -> FieldMapping:
    columns = [str(column) for column in df.columns]
    normalized = {column.strip().lower(): column for column in columns}
    selected: set[str] = set()
    mapping: dict[str, str | None] = {}

    for canonical in CANONICAL_FIELDS:
        candidate = None
        for alias in FIELD_ALIASES[canonical]:
            candidate = normalized.get(alias.lower())
            if candidate and candidate not in selected:
                break
            candidate = None
        mapping[canonical] = candidate
        if candidate:
            selected.add(candidate)

    return FieldMapping(mapping=mapping)


def apply_field_mapping(df: pd.DataFrame, field_mapping: FieldMapping) -> pd.DataFrame:
    columns = {str(column) for column in df.columns}
    selected: dict[str, str] = {}
    used: dict[str, str] = {}

    for canonical in CANONICAL_FIELDS:
        raw_column = field_mapping.mapping.get(canonical)
        if not raw_column:
            continue
        if raw_column not in columns:
            raise ValueError(f"字段映射失败：原始字段“{raw_column}”不存在。")
        if raw_column in used and used[raw_column] != canonical:
            raise ValueError(f"字段映射失败：原始字段“{raw_column}”被重复映射。")
        used[raw_column] = canonical
        selected[raw_column] = canonical

    mapped = df.rename(columns=selected).copy()
    duplicate_columns = mapped.columns[mapped.columns.duplicated()].tolist()
    if duplicate_columns:
        duplicates = ", ".join(str(column) for column in sorted(set(duplicate_columns)))
        raise ValueError(f"字段映射失败：映射后出现重复标准字段：{duplicates}。")
    return mapped
