from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models.result import AnalysisResult


def build_markdown_report(
    title: str,
    result: AnalysisResult,
    tables: dict[str, pd.DataFrame],
) -> str:
    lines = [
        f"# {title}",
        "",
        "## 核心结论",
        "",
        result.summary,
        "",
        "## 结构化结论",
        "",
    ]
    for claim in result.claims:
        lines.append(f"- {claim.text}（证据：{claim.evidence_id}）")

    if result.limitations:
        lines.extend(["", "## 限制说明", ""])
        lines.extend([f"- {item}" for item in result.limitations])

    for name, table in tables.items():
        lines.extend(["", f"## {name}", "", _dataframe_to_markdown(table)])

    lines.extend(["", "## 公式与代码", ""])
    for evidence in result.evidence:
        lines.extend(
            [
                f"### {evidence.evidence_id}",
                "",
                f"使用字段：{', '.join(evidence.fields)}",
                "",
                f"覆盖行数：{evidence.row_count}",
                "",
                "```text",
                evidence.formula,
                "```",
                "",
                "```python",
                evidence.code,
                "```",
            ]
        )
    return "\n".join(lines)


def save_markdown_report(markdown: str, output_path: str | Path = "docs/latest_analysis_report.md") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "无数据。"
    display = df.copy()
    display = display.head(50)
    columns = [str(column) for column in display.columns]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for record in display.astype(str).to_dict(orient="records"):
        rows.append("| " + " | ".join(record[column] for column in display.columns) + " |")
    return "\n".join(rows)
