from __future__ import annotations

from dataclasses import dataclass

from src.models.config import CleaningConfig


@dataclass(frozen=True)
class FollowupResult:
    supported: bool
    message: str
    cleaning_config: CleaningConfig


def apply_followup(question: str, current: CleaningConfig) -> FollowupResult:
    normalized = question.strip()
    if not normalized:
        return FollowupResult(False, "请输入追问内容。", current)

    if any(keyword in normalized for keyword in ["排除异常", "剔除异常", "去掉异常", "忽略异常"]):
        updated = current.model_copy(update={"anomaly_action": "exclude"})
        return FollowupResult(True, "已切换为排除 IQR 异常值后重新计算。", updated)

    if any(keyword in normalized for keyword in ["保留异常", "包含异常", "纳入异常"]):
        updated = current.model_copy(update={"anomaly_action": "include"})
        return FollowupResult(True, "已切换为纳入异常值后重新计算。", updated)

    if any(keyword in normalized for keyword in ["缺失金额按 0", "缺失金额按0", "空金额按 0", "空金额按0"]):
        updated = current.model_copy(update={"missing_amount": "zero"})
        return FollowupResult(True, "已切换为将缺失金额按 0 处理后重新计算。", updated)

    return FollowupResult(
        False,
        "当前 V6 追问暂支持：排除异常值、保留异常值、缺失金额按 0 后重新分析。",
        current,
    )
