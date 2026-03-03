from __future__ import annotations

import io
from typing import BinaryIO

import pandas as pd


def read_excel(file: BinaryIO | bytes) -> pd.DataFrame:
    """读取 Excel 文件并返回 DataFrame。

    支持 .xlsx / .xls 格式。自动去除列名前后空格。
    """
    if isinstance(file, bytes):
        file = io.BytesIO(file)
    df = pd.read_excel(file, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_columns(df: pd.DataFrame, required_columns: list[str]) -> list[str]:
    """校验 DataFrame 是否包含必要列，返回缺失列名列表。"""
    existing = {c.lower() for c in df.columns}
    missing = [c for c in required_columns if c.lower() not in existing]
    return missing


def get_column_case_insensitive(df: pd.DataFrame, col_name: str) -> str | None:
    """大小写不敏感地匹配列名，返回实际列名。"""
    for c in df.columns:
        if c.lower() == col_name.lower():
            return c
    return None


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """将 DataFrame 导出为 Excel 文件的 bytes。"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="优化结果")
    return buf.getvalue()
