from __future__ import annotations

from pathlib import Path

import pytest

from src.tools.file_parser import FileParseError, parse_file


def test_parse_sample_csv() -> None:
    parsed = parse_file(Path("data/sample_expenses_dirty.csv"))

    assert parsed.row_count > 700
    assert parsed.column_count == 9
    assert "amount" in parsed.dataframe.columns


def test_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(FileParseError, match="仅支持"):
        parse_file(path)
