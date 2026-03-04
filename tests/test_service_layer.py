"""Phase 2 测试：服务层行为一致性验证。

验证 OptimizationService 的编排逻辑与原 app.py 中直接调用 MainAgent 的行为一致。

用法：
    python tests/test_service_layer.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from agent.registry import AgentRegistry
from agent.main_agent import MainAgent, AgentResponse
from sub_agents.multi_q_expander import MultiQExpander
from services.optimization_service import OptimizationService, ExecutionRequest

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


def _make_service() -> tuple[OptimizationService, AgentRegistry]:
    """创建隔离的 service + registry 实例。"""
    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    original = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    service = OptimizationService(agent=agent)

    ma_mod.registry = original
    return service, reg


def test_service_execute_success():
    """正常请求通过 service 层执行，行为与直接调用 MainAgent 一致。"""
    print("[1] 服务层正常执行（无 LLM，仅校验阶段）")

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    orig_reg = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    service = OptimizationService(agent=agent)

    df = pd.DataFrame({"Q": ["问题1"], "A": ["答案1"]})

    request = ExecutionRequest(
        agent_id="multi_q_expander",
        df=df,
        user_params={"expand_count": 2, "style": "自动", "keywords": ""},
        api_key="test-key",
        base_url="https://test.example.com/v1",
        model="test-model",
    )

    resp = service.execute(request)
    check("返回 AgentResponse", isinstance(resp, AgentResponse))
    check("stage 不为空", bool(resp.stage))

    ma_mod.registry = orig_reg


def test_service_routing_error():
    """agent_id 不存在时，service 层正确返回路由错误。"""
    print("\n[2] 服务层路由错误")

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    orig_reg = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    service = OptimizationService(agent=agent)

    df = pd.DataFrame({"Q": ["q"], "A": ["a"]})
    request = ExecutionRequest(
        agent_id="nonexistent",
        df=df,
        user_params={},
    )
    resp = service.execute(request)
    check("返回失败", not resp.success)
    check("stage 为路由", resp.stage == "路由")
    check("error 非空", bool(resp.error))

    ma_mod.registry = orig_reg


def test_service_validation_error():
    """文件格式错误时，service 层正确返回校验错误。"""
    print("\n[3] 服务层校验错误")

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    orig_reg = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    service = OptimizationService(agent=agent)

    df_bad = pd.DataFrame({"Title": ["标题"]})
    request = ExecutionRequest(
        agent_id="multi_q_expander",
        df=df_bad,
        user_params={},
    )
    resp = service.execute(request)
    check("返回失败", not resp.success)
    check("stage 为校验", resp.stage == "校验")
    check("validation_errors 非空", bool(resp.validation_errors))

    ma_mod.registry = orig_reg


def test_service_params_injection():
    """验证 service 层正确注入 LLM 配置参数。"""
    print("\n[4] 参数注入验证")

    injected_params = {}

    class MockAgent:
        def execute(self, agent_id, df, params):
            injected_params.update(params)
            return AgentResponse(success=True, stage="完成")

    service = OptimizationService(agent=MockAgent())

    df = pd.DataFrame({"Q": ["q"], "A": ["a"]})
    request = ExecutionRequest(
        agent_id="test",
        df=df,
        user_params={"expand_count": 5},
        api_key="my-key",
        base_url="https://my-url/v1",
        model="my-model",
    )
    service.execute(request)

    check("_api_key 被注入", injected_params.get("_api_key") == "my-key")
    check("_base_url 被注入", injected_params.get("_base_url") == "https://my-url/v1")
    check("_model 被注入", injected_params.get("_model") == "my-model")
    check("用户参数保留", injected_params.get("expand_count") == 5)


def test_execution_request_defaults():
    """ExecutionRequest 默认值正确。"""
    print("\n[5] ExecutionRequest 默认值")

    df = pd.DataFrame({"Q": ["q"]})
    req = ExecutionRequest(
        agent_id="test",
        df=df,
        user_params={},
    )
    check("api_key 默认空", req.api_key == "")
    check("base_url 默认空", req.base_url == "")
    check("model 默认空", req.model == "")


def main():
    test_service_execute_success()
    test_service_routing_error()
    test_service_validation_error()
    test_service_params_injection()
    test_execution_request_defaults()

    print(f"\n{'=' * 40}")
    print(f"服务层测试：{passed} 通过，{failed} 失败")
    print(f"{'=' * 40}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
