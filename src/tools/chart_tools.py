from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.tools.analysis_tools import DepartmentYoyAnalysis
from src.tools.analysis_tools import AnomalyAnalysis, DepartmentSummaryAnalysis


def build_department_yoy_chart(analysis: DepartmentYoyAnalysis) -> go.Figure:
    chart_data = analysis.department_yoy.copy()
    chart_data["同比增长率"] = chart_data["yoy_growth"].fillna(0) * 100
    fig = px.bar(
        chart_data,
        x="department",
        y="同比增长率",
        color="status",
        labels={"department": "部门", "同比增长率": "同比增长率 (%)", "status": "状态"},
        title="各部门费用同比增长率",
    )
    fig.update_layout(height=360, margin=dict(l=24, r=24, t=56, b=24))
    return fig


def build_contribution_chart(analysis: DepartmentYoyAnalysis) -> go.Figure:
    chart_data = analysis.contribution_by_type.copy().head(8)
    chart_data["贡献率"] = chart_data["contribution_rate"] * 100
    fig = px.bar(
        chart_data,
        x="expense_type",
        y="increase",
        text="贡献率",
        labels={"expense_type": "费用类型", "increase": "新增费用", "贡献率": "贡献率 (%)"},
        title=f"{analysis.top_department} 新增费用类型贡献",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=360, margin=dict(l=24, r=24, t=56, b=24))
    return fig


def build_monthly_trend_chart(analysis: DepartmentYoyAnalysis) -> go.Figure:
    fig = px.line(
        analysis.monthly_trend,
        x="month",
        y="amount",
        color="department",
        labels={"month": "月份", "amount": "费用金额", "department": "部门"},
        title="各部门月度费用趋势",
    )
    fig.update_layout(height=360, margin=dict(l=24, r=24, t=56, b=24))
    return fig


def build_department_total_chart(analysis: DepartmentSummaryAnalysis) -> go.Figure:
    fig = px.bar(
        analysis.department_totals,
        x="department",
        y="total_amount",
        labels={"department": "部门", "total_amount": "费用总额"},
        title="各部门费用总额",
    )
    fig.update_layout(height=360, margin=dict(l=24, r=24, t=56, b=24))
    return fig


def build_anomaly_chart(analysis: AnomalyAnalysis) -> go.Figure:
    chart_data = analysis.cleaned_data.dropna(subset=["amount_clean"]).copy()
    chart_data["is_anomaly"] = chart_data["amount_clean"] > analysis.threshold
    fig = px.scatter(
        chart_data.reset_index(),
        x="index",
        y="amount_clean",
        color="is_anomaly",
        labels={"index": "记录序号", "amount_clean": "费用金额", "is_anomaly": "是否异常"},
        title="异常大额费用分布",
    )
    fig.add_hline(y=analysis.threshold, line_dash="dash", annotation_text=f"IQR 阈值 {analysis.threshold:,.0f}")
    fig.update_layout(height=380, margin=dict(l=24, r=24, t=56, b=24))
    return fig
