from __future__ import annotations

from sub_agents.base import SubAgentBase


class AgentRegistry:
    """子代理注册中心，维护 id → SubAgentBase 的映射。"""

    def __init__(self):
        self._agents: dict[str, SubAgentBase] = {}

    def register(self, agent: SubAgentBase) -> None:
        if agent.id in self._agents:
            raise ValueError(f"子代理 '{agent.id}' 已注册，不可重复注册")
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> SubAgentBase | None:
        return self._agents.get(agent_id)

    def list_all(self) -> list[SubAgentBase]:
        return list(self._agents.values())


registry = AgentRegistry()
