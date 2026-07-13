from __future__ import annotations

import pandas as pd

from src.tools.data_profiler import profile_dataframe


def test_profile_detects_core_quality_issues() -> None:
    df = pd.DataFrame(
        [
            {"date": "2025-01-01", "department": "市场部", "amount": "¥1,200.00"},
            {"date": "2025/01/02", "department": "市场部 ", "amount": " 300 "},
            {"date": "bad-date", "department": "销售部", "amount": ""},
            {"date": "2025-01-01", "department": "市场部", "amount": "¥1,200.00"},
        ]
    )

    profile = profile_dataframe(df)
    issues = "\n".join(profile.issues)

    assert profile.duplicate_count == 1
    assert "金额中包含货币符号" in issues
    assert "日期字段存在" in issues
    assert "日期格式不一致" in issues
    assert "疑似同义分类" in issues


def test_profile_marks_empty_column() -> None:
    df = pd.DataFrame({"date": ["2025-01-01"], "empty_notes": [None]})

    profile = profile_dataframe(df)
    issues = "\n".join(profile.issues)

    assert "以下字段全为空" in issues
