from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.services.evaluation_service import run_batch_evaluation, save_evaluation_outputs
from src.services.export_service import build_markdown_report, save_markdown_report
from src.services.followup_service import apply_followup
from src.services.llm_service import generate_analysis_plan, parse_user_intent
from src.services.observability import ExecutionLogger
from src.services.plan_service import validate_analysis_plan
from src.services.task_service import execute_analysis_task
from src.models.config import CANONICAL_FIELDS, CleaningConfig, FieldMapping
from src.tools.analysis_tools import AnalysisExecutionError
from src.tools.chart_tools import (
    build_anomaly_chart,
    build_contribution_chart,
    build_department_total_chart,
    build_department_yoy_chart,
    build_monthly_trend_chart,
)
from src.tools.data_profiler import profile_dataframe, profile_to_records
from src.tools.data_mapping import apply_field_mapping, suggest_field_mapping
from src.tools.file_parser import FileParseError, parse_file


SAMPLE_DATA_PATH = Path("data/sample_expenses_dirty.csv")
DEFAULT_QUESTION = "分析 2025 年各部门费用变化，找出同比增长最快的部门，并判断主要增长来自哪些费用类型。"


def main() -> None:
    st.set_page_config(page_title="InsightPilot", page_icon="IP", layout="wide")

    st.title("InsightPilot")
    st.caption("可验证、可解释的 AI 数据分析助手 | V6：可编辑、可追问、可观测")

    with st.sidebar:
        st.header("新建分析")
        uploaded_file = st.file_uploader("上传 CSV 或 XLSX", type=["csv", "xlsx"])
        use_sample = st.button("加载示例费用数据", use_container_width=True)

    parsed = None
    if uploaded_file is not None:
        try:
            parsed = parse_file(uploaded_file, uploaded_file.name)
        except FileParseError as exc:
            st.error(str(exc))
            return
    elif use_sample or SAMPLE_DATA_PATH.exists():
        try:
            parsed = parse_file(SAMPLE_DATA_PATH)
        except FileParseError as exc:
            st.error(str(exc))
            return

    if parsed is None:
        render_empty_state()
        return

    raw_df = parsed.dataframe
    _initialize_dataset_state(raw_df, parsed.name)
    field_mapping: FieldMapping = st.session_state["field_mapping"]
    try:
        df = apply_field_mapping(raw_df, field_mapping)
    except ValueError as exc:
        st.error(str(exc))
        return
    profile = profile_dataframe(df)

    st.subheader("文件概览")
    metric_cols = st.columns(5)
    metric_cols[0].metric("文件名", parsed.name)
    metric_cols[1].metric("行数", f"{parsed.row_count:,}")
    metric_cols[2].metric("列数", f"{parsed.column_count:,}")
    metric_cols[3].metric("重复记录", f"{profile.duplicate_count:,}")
    metric_cols[4].metric("数据问题", f"{len(profile.issues):,}")

    preview_tab, profile_tab, issue_tab, task_tab, result_tab, evaluation_tab = st.tabs(
        ["数据预览", "字段体检", "问题汇总", "分析任务", "结果与溯源", "批量评测"]
    )

    with preview_tab:
        st.dataframe(df.head(20), use_container_width=True)

    with profile_tab:
        profile_df = pd.DataFrame(profile_to_records(profile))
        st.dataframe(profile_df, use_container_width=True, hide_index=True)

    with issue_tab:
        if profile.issues:
            for issue in profile.issues:
                st.warning(issue)
        else:
            st.success("未发现明显数据质量问题。")

    with task_tab:
        render_task_creation(df, profile, raw_df)

    with result_tab:
        render_result_page(df)

    with evaluation_tab:
        render_evaluation_page(df)


def render_empty_state() -> None:
    st.subheader("开始一次费用数据分析")
    st.write("上传一份 CSV/XLSX，或使用内置示例数据查看数据体检效果。")
    st.info("第一阶段验收范围：上传、预览、字段类型识别、缺失值、重复值、金额格式和日期格式检测。")


def _initialize_dataset_state(df: pd.DataFrame, dataset_name: str) -> None:
    dataset_key = f"{dataset_name}:{df.shape[0]}:{','.join(map(str, df.columns))}"
    if st.session_state.get("dataset_key") == dataset_key:
        return

    st.session_state["dataset_key"] = dataset_key
    st.session_state["field_mapping"] = suggest_field_mapping(df)
    st.session_state["cleaning_config"] = CleaningConfig()
    st.session_state["intent"] = None
    st.session_state["plan"] = None
    st.session_state["plan_revision"] = 0
    st.session_state["analysis"] = None
    st.session_state["analysis_result"] = None
    st.session_state["validation_report"] = None
    st.session_state["execution_events"] = []
    st.session_state["followup_history"] = []


def render_mapping_editor(raw_df: pd.DataFrame) -> None:
    st.subheader("字段映射")
    current: FieldMapping = st.session_state["field_mapping"]
    raw_columns = [str(column) for column in raw_df.columns]
    options = ["不使用"] + raw_columns
    with st.form("field_mapping_form"):
        edited: dict[str, str | None] = {}
        columns = st.columns(2)
        for index, canonical in enumerate(CANONICAL_FIELDS):
            selected = current.mapping.get(canonical)
            selected_value = selected if selected in raw_columns else "不使用"
            with columns[index % 2]:
                value = st.selectbox(
                    f"标准字段：{canonical}",
                    options,
                    index=options.index(selected_value),
                    key=f"mapping_{canonical}",
                )
            edited[canonical] = None if value == "不使用" else value
        submitted = st.form_submit_button("保存字段映射")

    if submitted:
        try:
            st.session_state["field_mapping"] = FieldMapping(mapping=edited)
            st.session_state["intent"] = None
            st.session_state["plan"] = None
            st.session_state["analysis"] = None
            st.session_state["analysis_result"] = None
            st.session_state["validation_report"] = None
            st.success("字段映射已保存，请重新生成分析计划。")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render_cleaning_editor() -> None:
    st.subheader("清洗规则")
    current: CleaningConfig = st.session_state["cleaning_config"]
    with st.form("cleaning_config_form"):
        missing_amount = st.selectbox(
            "缺失或无法转换的金额",
            options=["exclude", "zero", "error"],
            format_func={"exclude": "排除", "zero": "按 0 处理", "error": "阻止执行"}.get,
            index=["exclude", "zero", "error"].index(current.missing_amount),
        )
        duplicate_rows = st.selectbox(
            "重复记录",
            options=["remove", "keep_first", "keep_last", "keep_all"],
            format_func={
                "remove": "去重",
                "keep_first": "保留第一条",
                "keep_last": "保留最后一条",
                "keep_all": "全部保留",
            }.get,
            index=["remove", "keep_first", "keep_last", "keep_all"].index(current.duplicate_rows),
        )
        anomaly_action = st.selectbox(
            "异常大额费用",
            options=["include", "exclude"],
            format_func={"include": "纳入分析", "exclude": "排除后分析"}.get,
            index=["include", "exclude"].index(current.anomaly_action),
        )
        normalize_text = st.checkbox("统一分类字段前后空格", value=current.normalize_text)
        submitted = st.form_submit_button("保存清洗规则")

    if submitted:
        st.session_state["cleaning_config"] = CleaningConfig(
            missing_amount=missing_amount,
            duplicate_rows=duplicate_rows,
            anomaly_action=anomaly_action,
            normalize_text=normalize_text,
        )
        st.session_state["analysis"] = None
        st.session_state["analysis_result"] = None
        st.session_state["validation_report"] = None
        st.success("清洗规则已保存。")


def render_task_creation(df: pd.DataFrame, profile, raw_df: pd.DataFrame) -> None:
    render_mapping_editor(raw_df)
    render_cleaning_editor()

    st.subheader("自然语言问题")
    with st.form("question_form"):
        question = st.text_area("输入分析问题", value=DEFAULT_QUESTION, height=96)
        submitted = st.form_submit_button("生成分析计划", type="primary")

    if submitted:
        intent = parse_user_intent(question, profile)
        plan = generate_analysis_plan(intent)
        st.session_state["intent"] = intent
        st.session_state["plan"] = plan
        st.session_state["plan_revision"] = int(st.session_state.get("plan_revision", 0)) + 1
        st.session_state["analysis_result"] = None

    intent = st.session_state.get("intent")
    plan = st.session_state.get("plan")
    if intent is None or plan is None:
        st.info("生成分析计划后，系统会先展示结构化意图和执行步骤，再由你确认是否运行。")
        return

    st.subheader("结构化意图")
    st.json(intent.model_dump())

    if intent.clarification_needed:
        st.warning(intent.clarification_question or "该问题需要进一步确认。")

    st.subheader("分析计划编辑")
    plan = render_plan_editor(plan, intent)

    if plan.warnings:
        for warning in plan.warnings:
            st.warning(warning)

    plan_errors = validate_analysis_plan(plan, intent)
    for error in plan_errors:
        st.error(error)

    execute_disabled = intent.clarification_needed or bool(plan_errors)
    if st.button("开始执行 Python 分析", type="primary", disabled=execute_disabled):
        logger = ExecutionLogger(model="rule_based")
        try:
            analysis, result, validation_report = execute_analysis_task(
                df,
                intent,
                plan=plan,
                cleaning_config=st.session_state["cleaning_config"],
                event_logger=logger,
            )
        except (AnalysisExecutionError, ValueError) as exc:
            st.error(str(exc))
            st.session_state["execution_events"] = logger.to_records()
            return

        st.session_state["analysis"] = analysis
        st.session_state["analysis_result"] = result
        st.session_state["validation_report"] = validation_report
        st.session_state["task_type"] = intent.task_type
        st.session_state["execution_events"] = logger.to_records()
        st.success("分析完成，请切换到“结果与溯源”查看。")

    if st.session_state.get("execution_events"):
        st.subheader("执行过程状态")
        st.dataframe(pd.DataFrame(st.session_state["execution_events"]), use_container_width=True, hide_index=True)


def render_plan_editor(plan, intent):
    revision = st.session_state.get("plan_revision", 0)
    edited_steps = []
    with st.form(f"plan_editor_{revision}"):
        for index, step in enumerate(plan.steps):
            st.markdown(f"**{step.step_id} · {step.action}**")
            col_enabled, col_order, col_description = st.columns([1, 1, 4])
            with col_enabled:
                enabled = st.checkbox("启用", value=step.enabled, key=f"enabled_{revision}_{step.step_id}")
            with col_order:
                order = st.number_input("顺序", min_value=1, max_value=len(plan.steps), value=index + 1, key=f"order_{revision}_{step.step_id}")
            with col_description:
                description = st.text_input("步骤描述", value=step.description, key=f"description_{revision}_{step.step_id}")
            edited_steps.append((int(order), step.model_copy(update={"enabled": enabled, "description": description})))
        submitted = st.form_submit_button("保存分析计划")

    if submitted:
        sorted_steps = [step for _, step in sorted(edited_steps, key=lambda item: item[0])]
        candidate = plan.model_copy(update={"steps": sorted_steps})
        errors = validate_analysis_plan(candidate, intent)
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state["plan"] = candidate
            st.session_state["analysis"] = None
            st.session_state["analysis_result"] = None
            st.session_state["validation_report"] = None
            st.success("分析计划已保存。")
            return candidate
    return st.session_state.get("plan", plan)


def render_result_page(df: pd.DataFrame) -> None:
    analysis = st.session_state.get("analysis")
    result = st.session_state.get("analysis_result")
    validation_report = st.session_state.get("validation_report")
    task_type = st.session_state.get("task_type", "department_yoy")
    if analysis is None or result is None:
        st.info("还没有分析结果。请先在“分析任务”中生成计划并执行。")
        return

    st.subheader("核心结论")
    st.write(result.summary)

    plan = st.session_state.get("plan")
    render_task_metrics_and_charts(task_type, analysis, plan)

    st.subheader("基于当前结果追问")
    with st.form("followup_form"):
        followup_question = st.text_input("追问", placeholder="例如：排除异常值后重新分析")
        followup_submitted = st.form_submit_button("应用追问并重算")
    if followup_submitted:
        intent = st.session_state.get("intent")
        current_config: CleaningConfig = st.session_state.get("cleaning_config", CleaningConfig())
        followup = apply_followup(followup_question, current_config)
        if not followup.supported:
            st.warning(followup.message)
        else:
            logger = ExecutionLogger(model="rule_based")
            try:
                analysis, result, validation_report = execute_analysis_task(
                    df,
                    intent,
                    plan=plan,
                    cleaning_config=followup.cleaning_config,
                    event_logger=logger,
                )
                st.session_state["cleaning_config"] = followup.cleaning_config
                st.session_state["analysis"] = analysis
                st.session_state["analysis_result"] = result
                st.session_state["validation_report"] = validation_report
                st.session_state["execution_events"] = logger.to_records()
                st.session_state.setdefault("followup_history", []).append(
                    {"question": followup_question, "message": followup.message}
                )
                st.success(followup.message)
                st.rerun()
            except (AnalysisExecutionError, ValueError) as exc:
                st.session_state["execution_events"] = logger.to_records()
                st.error(str(exc))

    st.caption(f"当前清洗口径：{st.session_state.get('cleaning_config', CleaningConfig()).model_dump()}")

    table_tab, validation_tab, claim_tab, evidence_tab, event_tab = st.tabs(["计算表", "自动校验", "结论校验口径", "公式与代码", "执行日志"])
    with table_tab:
        tables = get_result_tables(task_type, analysis)
        for title, table in tables.items():
            st.write(title)
            st.dataframe(table, use_container_width=True, hide_index=True)

    with validation_tab:
        if validation_report is None:
            st.info("暂无校验报告。")
        else:
            if validation_report.passed:
                st.success("所有发布前校验均已通过。")
            else:
                st.error("存在未通过的发布前校验。")
            validation_rows = [
                {
                    "校验项": check.name,
                    "状态": "通过" if check.passed else "失败",
                    "级别": check.severity,
                    "说明": check.message,
                    "细节": check.details,
                }
                for check in validation_report.checks
            ]
            st.dataframe(pd.DataFrame(validation_rows), use_container_width=True, hide_index=True)

    with claim_tab:
        for claim in result.claims:
            st.success(f"{claim.text} 证据：{claim.evidence_id}")
        for limitation in result.limitations:
            st.warning(limitation)

    with evidence_tab:
        report_markdown = build_markdown_report("InsightPilot 分析报告", result, get_result_tables(task_type, analysis))
        st.download_button(
            "下载 Markdown 分析报告",
            data=report_markdown,
            file_name="insightpilot_analysis_report.md",
            mime="text/markdown",
        )
        if st.button("保存报告到 docs/latest_analysis_report.md"):
            path = save_markdown_report(report_markdown)
            st.success(f"已保存：{path}")
        for evidence in result.evidence:
            with st.expander(evidence.evidence_id, expanded=True):
                st.write(f"使用字段：{', '.join(evidence.fields)}")
                st.write(f"覆盖行数：{evidence.row_count}")
                st.code(evidence.formula, language="text")
                st.code(evidence.code, language="python")

    with event_tab:
        events = st.session_state.get("execution_events", [])
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        else:
            st.info("暂无执行日志。")


def _format_department_yoy(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["amount_2024"] = formatted["amount_2024"].round(2)
    formatted["amount_2025"] = formatted["amount_2025"].round(2)
    formatted["increase"] = formatted["increase"].round(2)
    formatted["yoy_growth"] = formatted["yoy_growth"].apply(lambda value: "" if pd.isna(value) else f"{value * 100:.1f}%")
    return formatted


def _format_contribution(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["amount_2024"] = formatted["amount_2024"].round(2)
    formatted["amount_2025"] = formatted["amount_2025"].round(2)
    formatted["increase"] = formatted["increase"].round(2)
    formatted["contribution_rate"] = formatted["contribution_rate"].apply(lambda value: f"{value * 100:.1f}%")
    return formatted


def render_task_metrics_and_charts(task_type: str, analysis, plan=None) -> None:
    charts_enabled = plan is None or any(step.action == "generate_charts" and step.enabled for step in plan.steps)
    if task_type == "department_summary":
        metric_cols = st.columns(5)
        metric_cols[0].metric("费用总额", f"{analysis.total_amount:,.0f}")
        metric_cols[1].metric("费用最高部门", analysis.top_department)
        metric_cols[2].metric("覆盖行数", f"{analysis.covered_rows:,}")
        metric_cols[3].metric("排除行数", f"{analysis.excluded_rows:,}")
        metric_cols[4].metric("数据完整度", f"{analysis.data_completeness * 100:.1f}%")
        if charts_enabled:
            st.plotly_chart(build_department_total_chart(analysis), use_container_width=True)
        else:
            st.info("当前分析计划已停用图表生成。")
        return

    if task_type == "anomaly_detection":
        metric_cols = st.columns(5)
        metric_cols[0].metric("异常记录", f"{analysis.anomaly_count:,}")
        metric_cols[1].metric("最大异常金额", f"{analysis.max_anomaly_amount:,.0f}")
        metric_cols[2].metric("IQR 阈值", f"{analysis.threshold:,.0f}")
        metric_cols[3].metric("覆盖行数", f"{analysis.covered_rows:,}")
        metric_cols[4].metric("IQR", f"{analysis.iqr:,.0f}")
        if charts_enabled:
            st.plotly_chart(build_anomaly_chart(analysis), use_container_width=True)
        else:
            st.info("当前分析计划已停用图表生成。")
        return

    metric_cols = st.columns(5)
    metric_cols[0].metric("2025 总费用", f"{analysis.total_2025:,.0f}")
    yoy_text = "无法计算" if analysis.yoy_growth is None else f"{analysis.yoy_growth * 100:.1f}%"
    metric_cols[1].metric("整体同比", yoy_text)
    metric_cols[2].metric("增长最快部门", analysis.top_department)
    metric_cols[3].metric("覆盖行数", f"{analysis.covered_rows:,}")
    metric_cols[4].metric("排除行数", f"{analysis.excluded_rows:,}")
    if charts_enabled:
        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            st.plotly_chart(build_department_yoy_chart(analysis), use_container_width=True)
        with chart_col_2:
            st.plotly_chart(build_contribution_chart(analysis), use_container_width=True)
        st.plotly_chart(build_monthly_trend_chart(analysis), use_container_width=True)
    else:
        st.info("当前分析计划已停用图表生成。")


def get_result_tables(task_type: str, analysis) -> dict[str, pd.DataFrame]:
    if task_type == "department_summary":
        return {"各部门费用总额": _format_department_summary(analysis.department_totals)}
    if task_type == "anomaly_detection":
        return {"异常大额费用明细": _format_anomalies(analysis.anomaly_table)}
    return {
        "各部门同比结果": _format_department_yoy(analysis.department_yoy),
        f"{analysis.top_department} 费用类型贡献": _format_contribution(analysis.contribution_by_type),
    }


def _format_department_summary(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    formatted["total_amount"] = formatted["total_amount"].round(2)
    formatted["share"] = formatted["share"].apply(lambda value: f"{value * 100:.1f}%")
    return formatted


def _format_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for column in ["amount_clean", "threshold", "excess_amount"]:
        if column in formatted.columns:
            formatted[column] = formatted[column].round(2)
    return formatted


def _build_execution_steps(plan) -> list[dict[str, str]]:
    return [
        {
            "步骤": step.step_id,
            "动作": step.action,
            "工具": step.tool,
            "状态": "成功",
            "输出": step.expected_output,
        }
        for step in plan.steps
    ]


def render_evaluation_page(df: pd.DataFrame) -> None:
    st.subheader("测试集批量评测")
    st.write("基于 `data/test_cases.csv` 批量运行当前规则版意图解析、计划生成、Python 执行和发布前校验。")
    if st.button("运行批量评测并导出结果", type="primary"):
        evaluation = run_batch_evaluation(df)
        result_path, bad_case_path = save_evaluation_outputs(evaluation)
        st.session_state["evaluation"] = evaluation
        st.session_state["evaluation_paths"] = (result_path, bad_case_path)

    evaluation = st.session_state.get("evaluation")
    paths = st.session_state.get("evaluation_paths")
    if evaluation is None:
        st.info("运行后会生成 `docs/evaluation_results.csv` 和 `docs/bad_cases_log.csv`。")
        return

    summary_cols = st.columns(5)
    summary_cols[0].metric("用例数", int(evaluation.summary["case_count"]))
    summary_cols[1].metric("任务完成率", f"{evaluation.summary['task_completion_rate'] * 100:.1f}%")
    summary_cols[2].metric("校验通过率", f"{evaluation.summary['validation_pass_rate'] * 100:.1f}%")
    summary_cols[3].metric("澄清率", f"{evaluation.summary['clarification_rate'] * 100:.1f}%")
    summary_cols[4].metric("平均耗时", f"{evaluation.summary['avg_elapsed_ms']:.1f} ms")

    if paths:
        st.success(f"已导出：{paths[0]} 和 {paths[1]}")

    st.write("评测明细")
    st.dataframe(evaluation.cases, use_container_width=True, hide_index=True)

    st.write("Bad Case 日志")
    if evaluation.bad_cases.empty:
        st.success("当前测试集未产生失败用例。")
    else:
        st.dataframe(evaluation.bad_cases, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
