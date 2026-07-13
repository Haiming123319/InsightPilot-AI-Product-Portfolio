from __future__ import annotations

import pandas as pd

from src.models.config import CleaningConfig


class CleaningRuleError(ValueError):
    """Raised when a user-selected cleaning rule cannot be applied."""


def clean_expense_dataframe(df: pd.DataFrame, config: CleaningConfig | None = None) -> pd.DataFrame:
    config = config or CleaningConfig()
    cleaned = df.copy()

    if "amount" in cleaned.columns:
        cleaned["amount_clean"] = clean_amount_series(cleaned["amount"])

    if "date" in cleaned.columns:
        cleaned["date_clean"] = pd.to_datetime(cleaned["date"], errors="coerce", format="mixed")
        cleaned["year"] = cleaned["date_clean"].dt.year
        cleaned["month"] = cleaned["date_clean"].dt.to_period("M").astype(str)

    if config.missing_amount == "error" and "amount_clean" in cleaned.columns:
        missing_amount_count = int(cleaned["amount_clean"].isna().sum())
        if missing_amount_count:
            raise CleaningRuleError(f"金额字段存在 {missing_amount_count} 条无法转换或缺失记录，当前规则要求先处理。")
    if config.missing_amount == "zero" and "amount_clean" in cleaned.columns:
        cleaned["amount_clean"] = cleaned["amount_clean"].fillna(0)

    if config.normalize_text:
        for column in ["department", "expense_type", "region", "project", "approval_status"]:
            if column in cleaned.columns:
                cleaned[column] = cleaned[column].astype("string").str.strip()

    if config.duplicate_rows == "remove":
        cleaned = cleaned.drop_duplicates()
    elif config.duplicate_rows == "keep_first":
        cleaned = cleaned.drop_duplicates(keep="first")
    elif config.duplicate_rows == "keep_last":
        cleaned = cleaned.drop_duplicates(keep="last")

    if config.anomaly_action == "exclude" and "amount_clean" in cleaned.columns:
        valid_amounts = cleaned["amount_clean"].dropna()
        if not valid_amounts.empty:
            q1 = float(valid_amounts.quantile(0.25))
            q3 = float(valid_amounts.quantile(0.75))
            threshold = q3 + 1.5 * (q3 - q1)
            cleaned = cleaned[cleaned["amount_clean"] <= threshold]

    return cleaned.reset_index(drop=True)


def clean_amount_series(series: pd.Series) -> pd.Series:
    text = series.astype("string")
    normalized = (
        text.str.replace("人民币", "", regex=False)
        .str.replace(r"[¥￥$元,\s]", "", regex=True)
    )
    return pd.to_numeric(normalized, errors="coerce")
