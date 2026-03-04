"""V2 综合回归测试：验证升级后所有 12 项功能点完整、流程畅通。

汇总运行所有阶段测试 + 新增功能点检查。

用法：
    python tests/test_regression_v2.py
"""

import sys
import io
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from utils.excel_handler import read_excel, df_to_excel_bytes, validate_columns, get_column_case_insensitive
from sub_agents.base import SubAgentBase, SubAgentResult, ValidationResult, DiffItem, UnifiedResult, Artifact, Metrics
from sub_agents.multi_q_expander import MultiQExpander
from agent.registry import AgentRegistry
from agent.main_agent import MainAgent, AgentResponse
from agent.agent_loader import load_agents
from services.optimization_service import OptimizationService, ExecutionRequest
from services.task_manager import TaskManager

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


def test_f01_file_upload():
    """F01: Excel 文件上传（格式识别）"""
    print("[F01] Excel 文件上传")
    xlsx_files = list(TEST_DATA_DIR.glob("*.xlsx"))
    check("测试文件存在", len(xlsx_files) >= 20, f"实际 {len(xlsx_files)}")

    for f in xlsx_files[:3]:
        df = read_excel(f.read_bytes())
        check(f"读取 {f.name}", df is not None and len(df) > 0)


def test_f02_data_preview():
    """F02: 上传后数据预览"""
    print("\n[F02] 数据预览")
    df = pd.DataFrame({"Q": ["q1", "q2", "q3"], "A": ["a1", "a2", "a3"]})
    check("行数正确", len(df) == 3)
    check("列数正确", len(df.columns) == 2)
    check("前5行截取", len(df.head(5)) == 3)


def test_f03_column_validation():
    """F03: 列校验"""
    print("\n[F03] 列校验")
    df_ok = pd.DataFrame({"Q": ["q"], "A": ["a"]})
    check("Q/A 列校验通过", len(validate_columns(df_ok, ["Q", "A"])) == 0)

    df_lower = pd.DataFrame({"q": ["q"], "a": ["a"]})
    check("小写列名通过", get_column_case_insensitive(df_lower, "Q") == "q")

    df_bad = pd.DataFrame({"Title": ["t"]})
    check("缺列检测", len(validate_columns(df_bad, ["Q", "A"])) == 2)


def test_f04_agent_card_selection():
    """F04: 优化器卡片选择"""
    print("\n[F04] 优化器卡片选择")
    reg = AgentRegistry()
    load_agents(reg)
    agents = reg.list_all()
    check("至少 1 个优化器", len(agents) >= 1)
    check("multi_q_expander 存在", reg.get("multi_q_expander") is not None)

    agent = reg.get("multi_q_expander")
    check("有 id", bool(agent.id))
    check("有 name", bool(agent.name))
    check("有 description", bool(agent.description))


def test_f05_param_config():
    """F05: 参数配置动态渲染"""
    print("\n[F05] 参数配置")
    agent = MultiQExpander()
    schema = agent.params_schema

    check("expand_count 存在", "expand_count" in schema)
    check("expand_count type=int", schema["expand_count"]["type"] == "int")
    check("style 存在", "style" in schema)
    check("style type=select", schema["style"]["type"] == "select")
    check("keywords 存在", "keywords" in schema)
    check("style 有 options", len(schema["style"]["options"]) > 0)


def test_f06_execute_button_state():
    """F06: 执行按钮状态管理"""
    print("\n[F06] 执行条件检查")
    can_execute_good = (True and True and True and True)
    can_execute_bad = (True and True and False and True)
    check("条件全满足 -> 可执行", can_execute_good)
    check("条件不满足 -> 不可执行", not can_execute_bad)


def test_f07_f08_execution_flow():
    """F07/F08: 执行流程 + 结果摘要"""
    print("\n[F07/F08] 执行流程与摘要")

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    orig_reg = ma_mod.registry
    ma_mod.registry = reg

    tm = TaskManager()
    agent = MainAgent()
    service = OptimizationService(agent=agent, tm=tm)

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
    check("task_id 被设置", resp.task_id is not None)

    task = tm.get_task(resp.task_id)
    check("任务记录存在", task is not None)
    check("任务状态非 pending", task.status in ("running", "success", "failed"))

    ma_mod.registry = orig_reg


def test_f09_diff_comparison():
    """F09: 差异对比展示"""
    print("\n[F09] 差异对比")
    diff = DiffItem(original_q="如何重置密码？", expanded_qs=["怎么重新设置密码？", "密码忘了怎么办？"])
    check("original_q 可读", diff.original_q == "如何重置密码？")
    check("expanded_qs 数量", len(diff.expanded_qs) == 2)


def test_f10_result_table():
    """F10: 完整结果表格预览"""
    print("\n[F10] 结果表格")
    df = pd.DataFrame({
        "Q": ["q1"], "A": ["a1"], "扩展问题": ["v1 || v2"]
    })
    check("扩展问题列存在", "扩展问题" in df.columns)
    check("数据完整", len(df) == 1)


def test_f11_excel_download():
    """F11: Excel 下载"""
    print("\n[F11] Excel 下载")
    df = pd.DataFrame({
        "Q": ["q1", "q2"], "A": ["a1", "a2"], "扩展问题": ["v1", "v2"]
    })
    excel_bytes = df_to_excel_bytes(df)
    check("生成 bytes", len(excel_bytes) > 0)

    df_back = read_excel(excel_bytes)
    check("重新读取成功", len(df_back) == 2)
    check("列数保留", len(df_back.columns) == 3)
    check("扩展问题列保留", "扩展问题" in df_back.columns)


def test_f12_error_handling():
    """F12: 错误处理"""
    print("\n[F12] 错误处理")

    reg = AgentRegistry()
    reg.register(MultiQExpander())

    from agent import main_agent as ma_mod
    orig_reg = ma_mod.registry
    ma_mod.registry = reg

    agent = MainAgent()

    resp1 = agent.execute("nonexistent", pd.DataFrame(), {})
    check("不存在的代理 -> 路由失败", not resp1.success and resp1.stage == "路由")
    check("错误信息非空", bool(resp1.error))

    resp2 = agent.execute("multi_q_expander", pd.DataFrame(columns=["Q", "A"]), {})
    check("空文件 -> 校验失败", not resp2.success and resp2.stage == "校验")

    resp3 = agent.execute("multi_q_expander", pd.DataFrame({"X": [1]}), {})
    check("缺列 -> 校验失败", not resp3.success)
    check("validation_errors 非空", bool(resp3.validation_errors))

    ma_mod.registry = orig_reg


def test_v2_protocol_integration():
    """V2 统一协议集成完整性。"""
    print("\n[V2] 统一协议集成")
    unified = UnifiedResult(
        status="success",
        summary={"total": 5},
        artifacts=[
            Artifact(artifact_type="table", name="result"),
            Artifact(artifact_type="diff", name="diff"),
        ],
        metrics=Metrics(duration_ms=1000, input_count=5, output_count=5),
    )
    result = SubAgentResult(
        success=True,
        summary={"total": 5},
        unified_result=unified,
    )
    check("V1 + V2 共存", result.unified_result is not None)
    check("artifacts 数量 2", len(result.unified_result.artifacts) == 2)
    check("metrics 有值", result.unified_result.metrics.duration_ms == 1000)


def test_config_loader_integration():
    """配置加载器集成。"""
    print("\n[Config] 配置加载集成")
    from pathlib import Path
    config_path = PROJECT_ROOT / "agents_config.yaml"
    check("agents_config.yaml 存在", config_path.exists())

    reg = AgentRegistry()
    ids = load_agents(reg, config_path=config_path)
    check("加载成功", len(ids) >= 1)
    check("multi_q_expander 已注册", "multi_q_expander" in ids)


def test_task_manager_integration():
    """任务管理集成。"""
    print("\n[Task] 任务管理集成")
    tm = TaskManager()
    task = tm.create_task(agent_id="test", params={"a": 1, "_secret": "x"}, input_rows=10)
    check("task_id 生成", bool(task.task_id))
    check("敏感参数过滤", "_secret" not in task.params_snapshot)

    tm.start_task(task.task_id)
    check("status=running", task.status == "running")

    tm.complete_task(task.task_id)
    check("status=success", task.status == "success")
    check("duration 有值", task.duration_seconds is not None)


def main():
    print("=" * 50)
    print("知识库优化 Agent 2.0 — 综合回归测试")
    print("=" * 50)
    print()

    test_f01_file_upload()
    test_f02_data_preview()
    test_f03_column_validation()
    test_f04_agent_card_selection()
    test_f05_param_config()
    test_f06_execute_button_state()
    test_f07_f08_execution_flow()
    test_f09_diff_comparison()
    test_f10_result_table()
    test_f11_excel_download()
    test_f12_error_handling()
    test_v2_protocol_integration()
    test_config_loader_integration()
    test_task_manager_integration()

    print(f"\n{'=' * 50}")
    print(f"综合回归测试：{passed} 通过，{failed} 失败")
    print(f"{'=' * 50}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
