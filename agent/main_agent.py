from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from agent.registry import registry
from sub_agents.base import SubAgentResult, UnifiedResult, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """大 Agent 统一返回结构。"""
    success: bool
    stage: str
    # --- V1 字段（保留）---
    result: SubAgentResult | None = None
    error: str | None = None
    validation_errors: list[str] | None = None
    # --- V2 字段（新增，从 SubAgentResult.unified_result 透传）---
    unified_result: UnifiedResult | None = None
    # --- 任务追踪（由 service 层填充）---
    task_id: str | None = None


class MainAgent:
    """大 Agent：路由 → 后置校验 → 执行 → 结果汇总。

    核心原则：校验后置于选择之后。
    用户先上传文件并选择优化目的，大 Agent 再根据所选子代理的
    input_schema 来校验文件格式是否正确。
    """

    def execute(
        self,
        agent_id: str,
        df: pd.DataFrame,
        params: dict[str, Any],
    ) -> AgentResponse:
        # 1. 路由
        sub_agent = registry.get(agent_id)
        if sub_agent is None:
            available = [a.id for a in registry.list_all()]
            return AgentResponse(
                success=False,
                stage="路由",
                error=f"未找到子代理 '{agent_id}'，可用：{available}",
            )

        # 2. 后置校验（基于子代理的 input_schema）
        validation: ValidationResult = sub_agent.validate_input(df)
        if not validation.ok:
            return AgentResponse(
                success=False,
                stage="校验",
                validation_errors=validation.errors,
                error="文件校验未通过，请检查文件格式",
            )

        # 3. 执行
        try:
            result: SubAgentResult = sub_agent.run(df, params)
        except Exception as e:
            logger.exception("子代理 %s 执行异常", agent_id)
            return AgentResponse(
                success=False,
                stage="执行",
                error=f"子代理执行异常：{e}",
            )

        if not result.success:
            return AgentResponse(
                success=False,
                stage="执行",
                result=result,
                error=result.error or "子代理执行失败",
            )

        # 4. 结果汇总
        return AgentResponse(
            success=True,
            stage="完成",
            result=result,
            unified_result=result.unified_result,
        )


main_agent = MainAgent()
