from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


class FileParseError(ValueError):
    """Raised when an uploaded file cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedFile:
    name: str
    dataframe: pd.DataFrame
    size_bytes: int | None = None

    @property
    def row_count(self) -> int:
        return int(self.dataframe.shape[0])

    @property
    def column_count(self) -> int:
        return int(self.dataframe.shape[1])


def parse_file(file: str | Path | BinaryIO, filename: str | None = None) -> ParsedFile:
    """Parse CSV or XLSX into a DataFrame with consistent errors."""
    source_name = filename or getattr(file, "name", None)
    if not source_name:
        raise FileParseError("无法识别文件名。")

    extension = Path(source_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise FileParseError("仅支持 CSV 和 XLSX 文件。")

    try:
        if extension == ".csv":
            dataframe = pd.read_csv(file)
        else:
            dataframe = pd.read_excel(file)
    except Exception as exc:  # pragma: no cover - exact parser errors vary by engine
        raise FileParseError(f"文件读取失败：{exc}") from exc

    if dataframe.empty:
        raise FileParseError("文件为空，无法进行数据体检。")

    size_bytes = getattr(file, "size", None)
    return ParsedFile(name=Path(source_name).name, dataframe=dataframe, size_bytes=size_bytes)
