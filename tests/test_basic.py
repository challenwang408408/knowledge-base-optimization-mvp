"""基础自测脚本：验证文件解析、子代理协议、端到端处理。

用法：
    # 仅跑不依赖 LLM 的单元测试
    python tests/test_basic.py

    # 跑端到端测试（需要配置 .env 中的 LLM）
    python tests/test_basic.py --e2e
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from utils.excel_handler import read_excel, validate_columns, df_to_excel_bytes, get_column_case_insensitive
from sub_agents.base import SubAgentBase, ValidationResult, SubAgentResult
from sub_agents.multi_q_expander import MultiQExpander
from agent.registry import AgentRegistry
from agent.main_agent import MainAgent

TEST_DATA_DIR = Path(__file__).parent / "test_data"

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


def ensure_test_data():
    if not TEST_DATA_DIR.exists() or len(list(TEST_DATA_DIR.glob("*.xlsx"))) < 20:
        print("测试数据不存在，正在生成...")
        from tests.generate_test_data import main as gen_main
        gen_main()
        print()


def test_excel_handler():
    print("[1] Excel 工具测试")
    files = sorted(f for f in TEST_DATA_DIR.glob("*.xlsx") if not f.name.startswith("~$"))
    check("测试文件数量 >= 20", len(files) >= 20, f"实际 {len(files)}")

    for f in files:
        try:
            df = read_excel(f.read_bytes())
            check(f"读取 {f.name}", df is not None and len(df) > 0)
        except Exception as e:
            check(f"读取 {f.name}", False, str(e))

    df = pd.DataFrame({"Q": ["问题1"], "A": ["答案1"]})
    missing = validate_columns(df, ["Q", "A"])
    check("validate_columns — 正常列", len(missing) == 0)

    missing2 = validate_columns(df, ["Q", "A", "C"])
    check("validate_columns — 缺失列", "C" in missing2)

    df_lower = pd.DataFrame({"q": ["问题"], "a": ["答案"]})
    check(
        "get_column_case_insensitive",
        get_column_case_insensitive(df_lower, "Q") == "q",
    )

    excel_bytes = df_to_excel_bytes(df)
    check("df_to_excel_bytes", len(excel_bytes) > 0)
    df_back = read_excel(excel_bytes)
    check("Excel 往返一致", list(df_back.columns) == ["Q", "A"])


def test_sub_agent_protocol():
    print("\n[2] 子代理协议测试")
    agent = MultiQExpander()

    check("id 非空", bool(agent.id))
    check("name 非空", bool(agent.name))
    check("description 非空", bool(agent.description))
    check("input_schema 有 required_columns", "required_columns" in agent.input_schema)
    check("params_schema 非空", len(agent.params_schema) > 0)
    check("output_schema 非空", len(agent.output_schema) > 0)
    check("是 SubAgentBase 子类", isinstance(agent, SubAgentBase))


def test_validation():
    print("\n[3] 后置校验测试")
    agent = MultiQExpander()

    df_ok = pd.DataFrame({"Q": ["问题"], "A": ["答案"]})
    result = agent.validate_input(df_ok)
    check("正常文件校验通过", result.ok)

    df_missing = pd.DataFrame({"Title": ["标题"], "Content": ["内容"]})
    result2 = agent.validate_input(df_missing)
    check("缺少 Q/A 列校验失败", not result2.ok)
    check("返回错误信息", len(result2.errors) > 0)

    df_empty = pd.DataFrame(columns=["Q", "A"])
    result3 = agent.validate_input(df_empty)
    check("空数据校验失败", not result3.ok)

    df_lower = pd.DataFrame({"q": ["问题"], "a": ["答案"]})
    result4 = agent.validate_input(df_lower)
    check("小写列名校验通过", result4.ok)


def test_registry():
    print("\n[4] 注册中心测试")
    reg = AgentRegistry()
    agent = MultiQExpander()
    reg.register(agent)

    check("注册成功", reg.get("multi_q_expander") is not None)
    check("list_all", len(reg.list_all()) == 1)
    check("获取不存在的代理", reg.get("nonexistent") is None)

    try:
        reg.register(agent)
        check("重复注册报错", False, "应该抛出异常")
    except ValueError:
        check("重复注册报错", True)


def test_main_agent_routing():
    print("\n[5] 大 Agent 路由测试")
    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    original_registry = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    df = pd.DataFrame({"Q": ["问题"], "A": ["答案"]})

    # 路由到不存在的代理
    resp = agent.execute("nonexistent", df, {})
    check("路由失败返回错误", not resp.success and resp.stage == "路由")

    # 路由成功但文件格式错
    df_bad = pd.DataFrame({"Title": ["标题"]})
    resp2 = agent.execute("multi_q_expander", df_bad, {})
    check("校验失败返回错误", not resp2.success and resp2.stage == "校验")

    ma_mod.registry = original_registry


def test_e2e():
    """端到端测试：需要有效的 LLM 配置。"""
    print("\n[6] 端到端测试（需要 LLM）")

    from config import settings
    if not settings.LLM_API_KEY:
        print("  ⚠ 跳过：LLM_API_KEY 未配置")
        return

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    original_registry = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()
    files = sorted(f for f in TEST_DATA_DIR.glob("*.xlsx") if not f.name.startswith("~$"))

    e2e_passed = 0
    e2e_failed = 0
    for f in files:
        try:
            df = read_excel(f.read_bytes())
            params = {"expand_count": 2, "style": "自动", "keywords": ""}
            resp = agent.execute("multi_q_expander", df, params)
            if resp.success and resp.result and resp.result.output_df is not None:
                e2e_passed += 1
                print(f"  ✓ {f.name} — 成功 {resp.result.summary.get('success', 0)}/{resp.result.summary.get('total', 0)}")
            else:
                e2e_failed += 1
                print(f"  ✗ {f.name} — {resp.error}")
        except Exception as e:
            e2e_failed += 1
            print(f"  ✗ {f.name} — 异常: {e}")

    check(f"端到端: {e2e_passed}/{len(files)} 文件处理成功", e2e_passed == len(files))

    ma_mod.registry = original_registry


def main():
    global passed, failed

    ensure_test_data()

    test_excel_handler()
    test_sub_agent_protocol()
    test_validation()
    test_registry()
    test_main_agent_routing()

    if "--e2e" in sys.argv:
        test_e2e()

    print(f"\n{'=' * 40}")
    print(f"结果：{passed} 通过，{failed} 失败")
    print(f"{'=' * 40}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
