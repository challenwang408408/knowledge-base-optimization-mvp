"""优化服务层：编排逻辑从 UI 中下沉，职责清晰。

UI 层只需调用 OptimizationService 的方法，不再直接操作 MainAgent。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from agent.main_agent import MainAgent, AgentResponse, main_agent
from config import settings
from services.task_manager import TaskManager, Task, task_manager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRequest:
    """执行请求：封装 UI 层收集的所有输入。"""
    agent_id: str
    df: pd.DataFrame
    user_params: dict[str, Any]
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class OptimizationService:
    """优化编排服务，衔接 UI 层与 Agent 层。"""

    def __init__(
        self,
        agent: MainAgent | None = None,
        tm: TaskManager | None = None,
    ):
        self._agent = agent or main_agent
        self._task_manager = tm or task_manager

    def execute(self, request: ExecutionRequest) -> AgentResponse:
        """执行完整的优化流程。

        1. 创建任务
        2. 组装参数（注入 LLM 配置）
        3. 调用 MainAgent
        4. 更新任务状态
        5. 返回统一结果
        """
        task = self._task_manager.create_task(
            agent_id=request.agent_id,
            params=request.user_params,
            input_rows=len(request.df),
        )

        params = dict(request.user_params)
        params["_api_key"] = request.api_key or settings.LLM_API_KEY
        params["_base_url"] = request.base_url or settings.LLM_BASE_URL
        params["_model"] = request.model or settings.LLM_MODEL

        self._task_manager.start_task(task.task_id)

        try:
            response = self._agent.execute(
                agent_id=request.agent_id,
                df=request.df,
                params=params,
            )
        except Exception as e:
            self._task_manager.fail_task(task.task_id, str(e))
            raise

        if response.success:
            self._task_manager.complete_task(task.task_id)
        else:
            self._task_manager.fail_task(
                task.task_id,
                response.error or "未知错误",
            )

        response.task_id = task.task_id
        return response


optimization_service = OptimizationService()
