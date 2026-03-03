from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class DiffItem:
    original_q: str
    expanded_qs: list[str] = field(default_factory=list)


@dataclass
class SubAgentResult:
    success: bool
    output_df: pd.DataFrame | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    diff_items: list[DiffItem] = field(default_factory=list)
    error: str | None = None


class SubAgentBase(ABC):
    """子代理统一协议基类。

    所有子代理必须继承此类并实现全部抽象方法/属性。
    大 Agent 在路由到子代理后，先调用 validate_input 做后置校验，
    校验通过才调用 run 执行实际逻辑。
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """唯一标识，如 'multi_q_expander'"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """展示名称，如 '多Q扩展'"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """能力说明"""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """输入文件与字段要求（声明式）"""
        ...

    @property
    @abstractmethod
    def params_schema(self) -> dict:
        """可配置参数定义，格式:
        {
            "param_name": {
                "type": "int" | "str" | "select",
                "label": "展示名称",
                "description": "参数说明",
                "default": ...,
                "options": [...],   # type=select 时
                "min": ...,         # type=int 时
                "max": ...,         # type=int 时
            }
        }
        """
        ...

    @property
    @abstractmethod
    def output_schema(self) -> dict:
        """结果结构定义"""
        ...

    @abstractmethod
    def validate_input(self, df: pd.DataFrame) -> ValidationResult:
        """根据本子代理的 input_schema 校验输入数据。"""
        ...

    @abstractmethod
    def run(self, df: pd.DataFrame, params: dict) -> SubAgentResult:
        """执行子代理核心逻辑。"""
        ...
