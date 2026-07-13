from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import pandas as pd

from src.services.llm_service import generate_analysis_plan, parse_user_intent
from src.services.task_service import execute_analysis_task
from src.tools.analysis_tools import AnalysisExecutionError
from src.tools.data_profiler import profile_dataframe


@dataclass(frozen=True)
class EvaluationRun:
    cases: pd.DataFrame
    summary: dict[str, float | int]
    bad_cases: pd.DataFrame


def run_batch_evaluation(
    df: pd.DataFrame,
    cases_path: str | Path = "data/test_cases.csv",
    standard_answers_path: str | Path = "data/standard_answers.csv",
) -> EvaluationRun:
    cases = pd.read_csv(cases_path)
    standards = _load_standard_answers(standard_answers_path)
    profile = profile_dataframe(df)
    rows: list[dict[str, object]] = []
    bad_rows: list[dict[str, object]] = []

    for case in cases.itertuples(index=False):
        started = time.perf_counter()
        status = "passed"
        failure_reason = ""
        validation_passed = False
        clarification_needed = False
        task_understanding_passed = False
        expected_task_type = ""

        try:
            intent = parse_user_intent(str(case.question), profile)
            plan = generate_analysis_plan(intent)
            clarification_needed = intent.clarification_needed
            should_clarify = _case_expects_clarification(str(case.category), str(case.expected_behavior))
            standard = standards.get(str(case.id), {})
            expected_task_type = str(standard.get("expected_task_type", ""))
            task_understanding_passed = _matches_expected_task(intent.task_type, expected_task_type, clarification_needed)

            if clarification_needed:
                validation_passed = should_clarify
                if not should_clarify:
                    status = "failed"
                    failure_reason = intent.clarification_question or "意图解析请求澄清"
            else:
                analysis, result, report = execute_analysis_task(df, intent)
                validation_passed = report.passed
                if not report.passed:
                    status = "failed"
                    failure_reason = "; ".join(check.message for check in report.failed_checks)

                if should_clarify:
                    status = "failed"
                    validation_passed = False
                    failure_reason = "该用例期望请求澄清，但系统直接执行"

            plan_steps = len(plan.steps)
        except (AnalysisExecutionError, ValueError) as exc:
            status = "failed"
            failure_reason = str(exc)
            plan_steps = 0

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        row = {
            "id": case.id,
            "category": case.category,
            "question": case.question,
            "status": status,
            "clarification_needed": clarification_needed,
            "expected_task_type": expected_task_type,
            "actual_task_type": intent.task_type if "intent" in locals() else "",
            "task_understanding_passed": task_understanding_passed,
            "validation_passed": validation_passed,
            "plan_steps": plan_steps,
            "elapsed_ms": elapsed_ms,
            "failure_reason": failure_reason,
        }
        rows.append(row)
        if status != "passed":
            bad_rows.append(
                {
                    "case_id": case.id,
                    "category": case.category,
                    "question": case.question,
                    "failure_reason": failure_reason,
                    "improvement": _suggest_improvement(str(case.category), failure_reason),
                }
            )

    result_df = pd.DataFrame(rows)
    bad_df = pd.DataFrame(
        bad_rows,
        columns=["case_id", "category", "question", "failure_reason", "improvement"],
    )
    summary = {
        "case_count": int(len(result_df)),
        "task_completion_rate": _rate(result_df["status"] == "passed"),
        "task_understanding_accuracy": _rate(result_df["task_understanding_passed"]),
        "validation_pass_rate": _rate(result_df["validation_passed"]),
        "clarification_rate": _rate(result_df["clarification_needed"]),
        "avg_elapsed_ms": float(result_df["elapsed_ms"].mean()) if not result_df.empty else 0.0,
    }
    return EvaluationRun(cases=result_df, summary=summary, bad_cases=bad_df)


def save_evaluation_outputs(
    evaluation: EvaluationRun,
    output_dir: str | Path = "docs",
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "evaluation_results.csv"
    bad_case_path = output / "bad_cases_log.csv"
    evaluation.cases.to_csv(result_path, index=False)
    evaluation.bad_cases.to_csv(bad_case_path, index=False)
    return result_path, bad_case_path


def _case_expects_clarification(category: str, expected_behavior: str) -> bool:
    text = f"{category} {expected_behavior}"
    return any(keyword in text for keyword in ["错误字段", "不存在字段", "请求用户确认", "澄清"])


def _rate(mask: pd.Series) -> float:
    if mask.empty:
        return 0.0
    return round(float(mask.mean()), 4)


def _suggest_improvement(category: str, reason: str) -> str:
    if "字段" in reason or category == "错误字段":
        return "增加字段白名单、候选字段确认和低置信度澄清。"
    if "一致" in reason:
        return "确保结论、图表和计算表共用同一份结构化结果。"
    return "补充该问题类型的意图解析规则和标准答案。"


def _load_standard_answers(path: str | Path) -> dict[str, dict[str, object]]:
    standard_path = Path(path)
    if not standard_path.exists():
        return {}
    df = pd.read_csv(standard_path)
    return {str(row["id"]): row for row in df.to_dict(orient="records")}


def _matches_expected_task(actual_task_type: str, expected_task_type: str, clarification_needed: bool) -> bool:
    if not expected_task_type:
        return True
    if expected_task_type == "clarification":
        return clarification_needed
    return actual_task_type == expected_task_type and not clarification_needed
