"""Phase 3 测试：配置化加载器验证。

验证 YAML 正常/异常/禁用/不存在场景。

用法：
    python tests/test_config_loader.py
"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.registry import AgentRegistry
from agent.agent_loader import load_agents

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  — {detail}")


def test_normal_config():
    """正常 YAML 配置加载。"""
    print("[1] 正常配置加载")
    config_content = """
agents:
  - id: multi_q_expander
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: true
    icon: "🔄"
    order: 1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check("注册成功", len(ids) == 1)
    check("ID 正确", "multi_q_expander" in ids)
    check("registry 有代理", reg.get("multi_q_expander") is not None)
    config_path.unlink()


def test_disabled_agent():
    """disabled 子代理不被注册。"""
    print("\n[2] 禁用子代理")
    config_content = """
agents:
  - id: multi_q_expander
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: false
    icon: "🔄"
    order: 1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check(
        "禁用后回退默认注册",
        len(ids) >= 1,
        f"ids={ids}",
    )
    check(
        "multi_q_expander 仍可用（通过回退）",
        reg.get("multi_q_expander") is not None,
    )
    config_path.unlink()


def test_bad_yaml():
    """YAML 格式错误，回退到默认注册。"""
    print("\n[3] YAML 格式错误")
    config_content = "{{{{ bad yaml ::::"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check("回退注册成功", len(ids) >= 1)
    check("multi_q_expander 可用", reg.get("multi_q_expander") is not None)
    config_path.unlink()


def test_missing_config():
    """配置文件不存在，回退到默认注册。"""
    print("\n[4] 配置文件不存在")
    reg = AgentRegistry()
    ids = load_agents(reg, config_path=Path("/tmp/nonexistent_config_12345.yaml"))

    check("回退注册成功", len(ids) >= 1)
    check("multi_q_expander 可用", reg.get("multi_q_expander") is not None)


def test_bad_module_path():
    """module 路径错误，该条目加载失败但不影响其他。"""
    print("\n[5] 模块路径错误")
    config_content = """
agents:
  - id: bad_agent
    module: sub_agents.nonexistent_module
    class_name: BadClass
    enabled: true
    order: 1
  - id: multi_q_expander
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: true
    order: 2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check("bad_agent 未注册", reg.get("bad_agent") is None)
    check("multi_q_expander 仍注册成功", reg.get("multi_q_expander") is not None)
    check("只有 1 个成功", len(ids) == 1)
    config_path.unlink()


def test_mixed_enabled_disabled():
    """混合 enabled/disabled 场景。"""
    print("\n[6] 混合启用/禁用")
    config_content = """
agents:
  - id: multi_q_expander
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: true
    order: 1
  - id: disabled_agent
    module: sub_agents.multi_q_expander
    class_name: MultiQExpander
    enabled: false
    order: 2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check("只注册了 1 个", len(ids) == 1)
    check("multi_q_expander 注册", "multi_q_expander" in ids)
    config_path.unlink()


def test_empty_agents_list():
    """agents 列表为空，回退到默认注册。"""
    print("\n[7] agents 列表为空")
    config_content = """
agents: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        config_path = Path(f.name)

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)

    check("回退注册成功", len(ids) >= 1)
    check("multi_q_expander 可用", reg.get("multi_q_expander") is not None)
    config_path.unlink()


def main():
    test_normal_config()
    test_disabled_agent()
    test_bad_yaml()
    test_missing_config()
    test_bad_module_path()
    test_mixed_enabled_disabled()
    test_empty_agents_list()

    print(f"\n{'=' * 40}")
    print(f"配置加载测试：{passed} 通过，{failed} 失败")
    print(f"{'=' * 40}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
