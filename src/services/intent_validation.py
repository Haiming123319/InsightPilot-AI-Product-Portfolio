from __future__ import annotations

from src.models.intent import AnalysisIntent
from src.tools.data_profiler import DataProfile


SUPPORTED_TASK_TYPES = {"department_summary", "department_yoy", "anomaly_detection", "clarification"}
SUPPORTED_OPERATIONS = {
    "clean",
    "groupby",
    "sum",
    "year_over_year",
    "rank",
    "contribution",
    "iqr_anomaly_detection",
}
SUPPORTED_VISUALIZATIONS = {"bar_chart", "contribution_chart", "line_chart", "scatter_chart", "table"}


def validate_analysis_intent(intent: AnalysisIntent, profile: DataProfile) -> list[str]:
    """Validate model output against the dataset and product capability boundary."""

    available_fields = {column.name for column in profile.columns}
    errors: list[str] = []

    if intent.task_type not in SUPPORTED_TASK_TYPES:
        errors.append(f"不支持的任务类型：{intent.task_type}。")

    referenced_fields = set(intent.metrics) | set(intent.dimensions) | set(intent.filters)
    unknown_fields = sorted(referenced_fields - available_fields)
    if unknown_fields:
        errors.append(f"模型引用了不存在字段：{', '.join(unknown_fields)}。")

    unknown_operations = sorted(set(intent.operations) - SUPPORTED_OPERATIONS)
    if unknown_operations:
        errors.append(f"模型返回了未支持的分析操作：{', '.join(unknown_operations)}。")

    unknown_visualizations = sorted(set(intent.visualizations) - SUPPORTED_VISUALIZATIONS)
    if unknown_visualizations:
        errors.append(f"模型返回了未支持的图表类型：{', '.join(unknown_visualizations)}。")

    profile_by_name = {column.name: column for column in profile.columns}
    for field in intent.metrics:
        column = profile_by_name.get(field)
        if column and column.semantic_type not in {"currency", "number", "金额", "数值"}:
            errors.append(f"指标字段 {field} 的类型为 {column.semantic_type or column.inferred_type}，不适合数值计算。")

    if intent.task_type == "department_yoy":
        errors.extend(_validate_yoy_scope(intent, profile))

    return errors


def _validate_yoy_scope(intent: AnalysisIntent, profile: DataProfile) -> list[str]:
    errors: list[str] = []
    if len(intent.time_range) not in {0, 2}:
        errors.append("同比分析的时间范围必须包含两个时间周期。")
        return errors
    if not profile.date_range:
        errors.append("数据画像无法识别日期范围，不能安全执行同比分析。")
        return errors

    start_year = int(profile.date_range[0][:4])
    end_year = int(profile.date_range[1][:4])
    requested_years = {int(value[:4]) for value in intent.time_range}
    if requested_years and not all(start_year <= year <= end_year for year in requested_years):
        errors.append(
            f"模型请求的时间范围 {', '.join(map(str, sorted(requested_years)))} 不在数据范围 "
            f"{profile.date_range[0]} 至 {profile.date_range[1]} 内。"
        )
    if end_year <= start_year:
        errors.append("数据至少需要覆盖两个时间周期，才能计算同比。")
    return errors
