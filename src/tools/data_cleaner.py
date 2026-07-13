from __future__ import annotations

import pandas as pd


def clean_expense_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()

    if "amount" in cleaned.columns:
        cleaned["amount_clean"] = clean_amount_series(cleaned["amount"])

    if "date" in cleaned.columns:
        cleaned["date_clean"] = pd.to_datetime(cleaned["date"], errors="coerce", format="mixed")
        cleaned["year"] = cleaned["date_clean"].dt.year
        cleaned["month"] = cleaned["date_clean"].dt.to_period("M").astype(str)

    for column in ["department", "expense_type", "region", "project", "approval_status"]:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()

    return cleaned.drop_duplicates().reset_index(drop=True)


def clean_amount_series(series: pd.Series) -> pd.Series:
    text = series.astype("string")
    normalized = (
        text.str.replace("人民币", "", regex=False)
        .str.replace(r"[¥￥$元,\s]", "", regex=True)
    )
    return pd.to_numeric(normalized, errors="coerce")
