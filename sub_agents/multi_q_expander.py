from __future__ import annotations

import json
import logging
import time
from typing import Any

import pandas as pd

from sub_agents.base import (
    SubAgentBase,
    SubAgentResult,
    ValidationResult,
    DiffItem,
)
from utils.excel_handler import get_column_case_insensitive, validate_columns
from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的知识库优化助手。你的任务是为给定的问题（Q）生成多种不同的表达方式（变体问法），
使知识库能覆盖更多用户可能的提问方式。

要求：
1. 生成的变体必须与原始问题语义一致。
2. 变体之间应在措辞、句式、口语/书面程度上有差异。
3. 不要改变原始问题的核心意图。
4. 严格按照 JSON 数组格式返回，不要包含其他内容。"""


def _build_user_prompt(
    question: str,
    answer: str,
    count: int,
    style: str,
    keywords: str,
) -> str:
    parts = [
        f"原始问题：{question}",
        f"参考答案：{answer}",
        f"请生成 {count} 条不同表达的变体问题。",
    ]
    if style:
        parts.append(f"语气风格要求：{style}")
    if keywords:
        parts.append(f"领域关键词（变体中尽量自然融入）：{keywords}")
    parts.append('请以 JSON 数组格式返回，例如 ["变体1", "变体2", ...]')
    return "\n".join(parts)


def _parse_variants(raw: str) -> list[str]:
    """从 LLM 返回的文本中解析变体列表。"""
    text = raw.strip()
    # 尝试找到 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            arr = json.loads(text[start : end + 1])
            if isinstance(arr, list):
                return [str(item).strip() for item in arr if str(item).strip()]
        except json.JSONDecodeError:
            pass
    # fallback: 按行分割
    lines = [
        line.strip().lstrip("0123456789.-、）) ").strip('"').strip("'")
        for line in text.splitlines()
        if line.strip()
    ]
    return [l for l in lines if l]


class MultiQExpander(SubAgentBase):
    """多Q扩展子代理：为每条问题生成多种变体表达。"""

    @property
    def id(self) -> str:
        return "multi_q_expander"

    @property
    def name(self) -> str:
        return "多Q扩展"

    @property
    def description(self) -> str:
        return (
            "为知识库中的每条问题（Q）生成多种不同的表达方式，"
            "提升知识库的召回覆盖率。"
        )

    @property
    def input_schema(self) -> dict:
        return {
            "file_type": "excel",
            "required_columns": ["Q", "A"],
            "description": "Excel 文件需包含 Q（问题）列和 A（答案）列",
        }

    @property
    def params_schema(self) -> dict:
        return {
            "expand_count": {
                "type": "int",
                "label": "扩展倍率",
                "description": "每条问题生成的变体数量",
                "default": 3,
                "min": 1,
                "max": 10,
            },
            "style": {
                "type": "select",
                "label": "语气风格",
                "description": "生成变体的语气风格偏好",
                "default": "自动",
                "options": ["自动", "简洁", "口语化", "正式", "混合"],
            },
            "keywords": {
                "type": "str",
                "label": "领域关键词",
                "description": "可选，用逗号分隔多个关键词",
                "default": "",
            },
        }

    @property
    def output_schema(self) -> dict:
        return {
            "output_df": "包含原始列 + 扩展Q列的 DataFrame",
            "summary": {
                "total": "总处理条数",
                "success": "成功条数",
                "failed": "失败条数",
                "elapsed_seconds": "耗时（秒）",
            },
            "diff_items": "[{original_q, expanded_qs}]",
        }

    def validate_input(self, df: pd.DataFrame) -> ValidationResult:
        errors: list[str] = []
        if df.empty:
            errors.append("上传的文件为空，没有数据行")
            return ValidationResult(ok=False, errors=errors)

        missing = validate_columns(df, self.input_schema["required_columns"])
        if missing:
            errors.append(
                f"缺少必要列：{', '.join(missing)}。"
                f"当前列名：{', '.join(df.columns.tolist())}"
            )
        return ValidationResult(ok=len(errors) == 0, errors=errors)

    def run(self, df: pd.DataFrame, params: dict) -> SubAgentResult:
        from config import settings

        llm = LLMClient(
            api_key=params.get("_api_key", settings.LLM_API_KEY),
            base_url=params.get("_base_url", settings.LLM_BASE_URL),
            model=params.get("_model", settings.LLM_MODEL),
        )

        expand_count = params.get("expand_count", 3)
        style = params.get("style", "自动")
        if style == "自动":
            style = ""
        keywords = params.get("keywords", "")

        q_col = get_column_case_insensitive(df, "Q")
        a_col = get_column_case_insensitive(df, "A")
        if not q_col or not a_col:
            return SubAgentResult(success=False, error="无法定位 Q/A 列")

        start_time = time.time()
        total = len(df)
        success_count = 0
        failed_count = 0
        all_expanded: list[str] = []
        diff_items: list[DiffItem] = []
        error_details: list[str] = []

        for idx, row in df.iterrows():
            question = str(row[q_col]).strip()
            answer = str(row[a_col]).strip()

            if not question or question.lower() == "nan":
                all_expanded.append("")
                failed_count += 1
                error_details.append(f"行 {idx + 2}: 问题为空")
                diff_items.append(DiffItem(original_q="(空)", expanded_qs=[]))
                continue

            try:
                user_msg = _build_user_prompt(
                    question, answer, expand_count, style, keywords
                )
                raw = llm.chat_completion(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.8,
                )
                variants = _parse_variants(raw)
                if not variants:
                    raise ValueError("模型返回内容无法解析为变体列表")

                all_expanded.append(" || ".join(variants))
                diff_items.append(DiffItem(original_q=question, expanded_qs=variants))
                success_count += 1
            except Exception as e:
                logger.warning("行 %d 处理失败：%s", idx + 2, e)
                all_expanded.append("")
                diff_items.append(DiffItem(original_q=question, expanded_qs=[]))
                failed_count += 1
                error_details.append(f"行 {idx + 2}: {e}")

        elapsed = round(time.time() - start_time, 2)

        output_df = df.copy()
        output_df["扩展问题"] = all_expanded

        summary: dict[str, Any] = {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "elapsed_seconds": elapsed,
            "expand_count": expand_count,
            "style": style or "自动",
            "keywords": keywords or "(无)",
        }
        if error_details:
            summary["error_details"] = error_details

        return SubAgentResult(
            success=True,
            output_df=output_df,
            summary=summary,
            diff_items=diff_items,
        )
