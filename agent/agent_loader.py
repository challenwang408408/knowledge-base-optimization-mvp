"""配置驱动的子代理加载器。

从 agents_config.yaml 读取配置，动态导入并注册子代理。
若配置文件不存在或格式错误，回退到硬编码默认注册。
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from agent.registry import AgentRegistry

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "agents_config.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 配置文件。"""
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _fallback_register(registry: AgentRegistry) -> None:
    """硬编码回退：当配置加载失败时，注册默认子代理。"""
    from sub_agents.multi_q_expander import MultiQExpander
    try:
        registry.register(MultiQExpander())
        logger.info("回退模式：已注册默认子代理 MultiQExpander")
    except ValueError:
        pass


def load_agents(
    registry: AgentRegistry,
    config_path: Path | None = None,
) -> list[str]:
    """从配置文件加载子代理到 registry。

    Returns:
        成功注册的子代理 ID 列表。
    """
    path = config_path or DEFAULT_CONFIG_PATH
    errors: list[str] = []

    if not path.exists():
        logger.warning("配置文件 %s 不存在，回退到默认注册", path)
        _fallback_register(registry)
        return [a.id for a in registry.list_all()]

    try:
        config = _load_yaml(path)
    except Exception as e:
        logger.error("配置文件解析失败：%s，回退到默认注册", e)
        _fallback_register(registry)
        return [a.id for a in registry.list_all()]

    agent_configs = config.get("agents", [])
    if not isinstance(agent_configs, list):
        logger.error("配置格式错误：agents 应为列表，回退到默认注册")
        _fallback_register(registry)
        return [a.id for a in registry.list_all()]

    registered_ids: list[str] = []

    for entry in agent_configs:
        agent_id = entry.get("id", "<unknown>")
        enabled = entry.get("enabled", True)

        if not enabled:
            logger.info("子代理 %s 已禁用，跳过", agent_id)
            continue

        module_path = entry.get("module")
        class_name = entry.get("class_name")

        if not module_path or not class_name:
            errors.append(f"子代理 {agent_id} 配置缺少 module 或 class_name")
            continue

        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            instance = cls()
            registry.register(instance)
            registered_ids.append(agent_id)
            logger.info("已注册子代理: %s (%s.%s)", agent_id, module_path, class_name)
        except Exception as e:
            errors.append(f"子代理 {agent_id} 加载失败：{e}")
            logger.error("子代理 %s 加载失败：%s", agent_id, e)

    if errors:
        for err in errors:
            logger.warning(err)

    if not registered_ids:
        logger.warning("无子代理成功注册，回退到默认注册")
        _fallback_register(registry)
        registered_ids = [a.id for a in registry.list_all()]

    return registered_ids
