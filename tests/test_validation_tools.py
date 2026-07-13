from __future__ import annotations

import pandas as pd

from src.models.result import AnalysisClaim
from src.services.evaluation_service import run_batch_evaluation
from src.services.task_service import execute_department_yoy_task
from src.tools.validation_tools import validate_analysis_result, validate_fields


def test_validation_report_passes_for_python_result() -> None:
    df = pd.DataFrame(
        [
            {"date": "2024-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "100"},
            {"date": "2025-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "180"},
            {"date": "2024-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "200"},
            {"date": "2025-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "210"},
        ]
    )

    analysis, result, report = execute_department_yoy_task(df)

    assert report.passed is True
    assert validate_analysis_result(df, analysis, result).passed is True


def test_claim_consistency_catches_wrong_ranking_claim() -> None:
    df = pd.DataFrame(
        [
            {"date": "2024-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "100"},
            {"date": "2025-01-01", "department": "市场部", "expense_type": "差旅费", "amount": "180"},
            {"date": "2024-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "200"},
            {"date": "2025-01-01", "department": "销售部", "expense_type": "广告投放", "amount": "210"},
        ]
    )
    analysis, result, _ = execute_department_yoy_task(df)
    result.claims[0] = AnalysisClaim(
        text="销售部排名第一。",
        entity="销售部",
        metric="yoy_growth",
        value=5.0,
        unit="%",
        evidence_id="table_department_yoy",
    )

    report = validate_analysis_result(df, analysis, result)

    assert report.passed is False
    assert any(check.check_id == "claim_consistency" for check in report.failed_checks)


def test_field_validation_catches_missing_required_fields() -> None:
    check = validate_fields(pd.DataFrame({"department": ["市场部"]}))

    assert check.passed is False
    assert "缺少必要字段" in check.message


def test_batch_evaluation_logs_bad_cases() -> None:
    df = pd.read_csv("data/sample_expenses_dirty.csv")

    evaluation = run_batch_evaluation(df)

    assert evaluation.summary["case_count"] >= 30
    assert evaluation.summary["task_completion_rate"] >= 0.9
    assert "TC006" not in evaluation.bad_cases["case_id"].tolist()
    assert "TC001" not in evaluation.bad_cases["case_id"].tolist()
    assert "TC005" not in evaluation.bad_cases["case_id"].tolist()
