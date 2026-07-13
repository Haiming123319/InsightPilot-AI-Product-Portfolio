from __future__ import annotations

from src.models.intent import AnalysisIntent
from src.models.plan import AnalysisPlan


REQUIRED_ACTIONS = {
    "department_summary": {"clean_amount", "group_department_total", "validate_result", "explain_result"},
    "department_yoy": {"clean_amount", "clean_date", "group_department_yoy", "validate_result", "explain_result"},
    "anomaly_detection": {"clean_amount", "detect_amount_anomalies", "validate_result", "explain_result"},
}


def validate_analysis_plan(plan: AnalysisPlan, intent: AnalysisIntent) -> list[str]:
    errors: list[str] = []
    if not plan.steps:
        return ["分析计划不能为空。"]

    step_ids = [step.step_id for step in plan.steps]
    duplicate_ids = sorted({step_id for step_id in step_ids if step_ids.count(step_id) > 1})
    if duplicate_ids:
        errors.append(f"计划步骤 ID 重复：{', '.join(duplicate_ids)}。")

    enabled_actions = {step.action for step in plan.steps if step.enabled}
    missing_actions = sorted(REQUIRED_ACTIONS.get(intent.task_type, set()) - enabled_actions)
    if missing_actions:
        errors.append(f"以下必要步骤不能停用：{', '.join(missing_actions)}。")

    action_positions = {step.action: index for index, step in enumerate(plan.steps) if step.enabled}
    if "validate_result" in action_positions and "explain_result" in action_positions:
        if action_positions["validate_result"] > action_positions["explain_result"]:
            errors.append("结果校验必须在结论生成之前完成。")
    return errors
