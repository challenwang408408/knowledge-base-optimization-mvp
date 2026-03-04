"""Phase 1 测试：V1/V2 协议兼容性验证。

验证新旧协议字段共存，UI 读取旧字段不报错，新字段正确填充。

用法：
    python tests/test_protocol_compat.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from sub_agents.base import (
    SubAgentResult,
    DiffItem,
    UnifiedResult,
    Artifact,
    Metrics,
    ValidationResult,
)
from sub_agents.multi_q_expander import MultiQExpander
from agent.main_agent import MainAgent, AgentResponse
from agent.registry import AgentRegistry

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


def test_v1_fields_intact():
    """V1 旧字段仍存在且可正常读取。"""
    print("[1] V1 字段完整性")
    result = SubAgentResult(
        success=True,
        output_df=pd.DataFrame({"Q": ["q1"], "A": ["a1"]}),
        summary={"total": 1, "success": 1},
        diff_items=[DiffItem(original_q="q1", expanded_qs=["q1v1"])],
    )
    check("success 字段可读", result.success is True)
    check("output_df 字段可读", result.output_df is not None)
    check("summary 字段可读", result.summary["total"] == 1)
    check("diff_items 字段可读", len(result.diff_items) == 1)
    check("diff_items[0].original_q", result.diff_items[0].original_q == "q1")
    check("error 字段默认 None", result.error is None)
    check("unified_result 默认 None", result.unified_result is None)


def test_v2_fields_new():
    """V2 新字段可正确创建和读取。"""
    print("\n[2] V2 新字段创建与读取")
    artifact = Artifact(
        artifact_type="table",
        name="测试表",
        mime_type="application/json",
        data={"rows": 5},
    )
    check("Artifact 创建", artifact.artifact_type == "table")
    check("Artifact name", artifact.name == "测试表")
    check("Artifact data", artifact.data == {"rows": 5})
    check("Artifact download_path 默认空", artifact.download_path == "")

    metrics = Metrics(duration_ms=1500, input_count=10, output_count=8)
    check("Metrics 创建", metrics.duration_ms == 1500)
    check("Metrics input_count", metrics.input_count == 10)

    unified = UnifiedResult(
        status="success",
        summary={"total": 10},
        artifacts=[artifact],
        metrics=metrics,
        warnings=["行3处理失败"],
        errors=[],
    )
    check("UnifiedResult status", unified.status == "success")
    check("UnifiedResult artifacts 数量", len(unified.artifacts) == 1)
    check("UnifiedResult metrics", unified.metrics.output_count == 8)
    check("UnifiedResult warnings", len(unified.warnings) == 1)
    check("UnifiedResult errors 为空", len(unified.errors) == 0)


def test_v1_v2_coexist():
    """V1 和 V2 字段在同一个 SubAgentResult 中共存。"""
    print("\n[3] V1 + V2 共存")
    unified = UnifiedResult(
        status="success",
        summary="测试摘要",
        artifacts=[Artifact(artifact_type="diff", name="diff")],
        metrics=Metrics(duration_ms=500, input_count=3, output_count=3),
    )
    result = SubAgentResult(
        success=True,
        output_df=pd.DataFrame({"Q": ["q"], "A": ["a"]}),
        summary={"total": 3},
        diff_items=[DiffItem(original_q="q", expanded_qs=["v1", "v2"])],
        unified_result=unified,
    )
    check("V1 success 可读", result.success is True)
    check("V1 summary 可读", result.summary["total"] == 3)
    check("V1 diff_items 可读", len(result.diff_items) == 1)
    check("V2 unified_result 非 None", result.unified_result is not None)
    check("V2 status", result.unified_result.status == "success")
    check("V2 artifacts 数量", len(result.unified_result.artifacts) == 1)
    check("V2 metrics", result.unified_result.metrics.duration_ms == 500)


def test_agent_response_v2():
    """AgentResponse 可透传 V2 字段。"""
    print("\n[4] AgentResponse V2 透传")
    unified = UnifiedResult(status="success", summary="ok")
    sub_result = SubAgentResult(
        success=True,
        summary={"total": 1},
        unified_result=unified,
    )
    resp = AgentResponse(
        success=True,
        stage="完成",
        result=sub_result,
        unified_result=unified,
    )
    check("AgentResponse.unified_result 非 None", resp.unified_result is not None)
    check("AgentResponse.unified_result.status", resp.unified_result.status == "success")
    check("AgentResponse.result 仍可读", resp.result.summary["total"] == 1)


def test_ui_reads_only_v1():
    """模拟 UI 只读 V1 字段的场景，确保不报错。"""
    print("\n[5] 模拟 UI 只读 V1 字段")
    unified = UnifiedResult(status="success", summary="ok")
    result = SubAgentResult(
        success=True,
        output_df=pd.DataFrame({"Q": ["q"], "A": ["a"], "扩展问题": ["v1 || v2"]}),
        summary={"total": 1, "success": 1, "failed": 0, "elapsed_seconds": 0.5},
        diff_items=[DiffItem(original_q="q", expanded_qs=["v1", "v2"])],
        unified_result=unified,
    )
    try:
        _ = result.summary.get("total", 0)
        _ = result.summary.get("success", 0)
        _ = result.summary.get("failed", 0)
        _ = result.summary.get("elapsed_seconds", 0)
        _ = result.diff_items[0].original_q
        _ = result.diff_items[0].expanded_qs
        _ = result.output_df.columns.tolist()
        check("V1 读取全部成功（无异常）", True)
    except Exception as e:
        check("V1 读取全部成功（无异常）", False, str(e))


def test_ui_reads_only_v2():
    """模拟 UI 只读 V2 字段的场景，确保不报错。"""
    print("\n[6] 模拟 UI 只读 V2 字段")
    unified = UnifiedResult(
        status="success",
        summary={"total": 5, "success": 4, "failed": 1},
        artifacts=[
            Artifact(artifact_type="table", name="结果表", data="<df>"),
            Artifact(artifact_type="diff", name="差异", data=[{"q": "q1"}]),
        ],
        metrics=Metrics(duration_ms=2000, input_count=5, output_count=4),
        warnings=["行3失败"],
    )
    result = SubAgentResult(success=True, unified_result=unified)
    try:
        ur = result.unified_result
        _ = ur.status
        _ = ur.summary
        _ = ur.artifacts[0].artifact_type
        _ = ur.artifacts[0].name
        _ = ur.artifacts[1].data
        _ = ur.metrics.duration_ms
        _ = ur.warnings
        check("V2 读取全部成功（无异常）", True)
    except Exception as e:
        check("V2 读取全部成功（无异常）", False, str(e))


def test_multi_q_expander_protocol():
    """验证 MultiQExpander 协议层面兼容性（不调用 LLM）。"""
    print("\n[7] MultiQExpander 协议兼容")
    agent = MultiQExpander()
    check("id 存在", bool(agent.id))
    check("name 存在", bool(agent.name))

    df = pd.DataFrame({"Q": ["问题"], "A": ["答案"]})
    v = agent.validate_input(df)
    check("validate_input 返回 ValidationResult", isinstance(v, ValidationResult))
    check("校验通过", v.ok)


def main():
    test_v1_fields_intact()
    test_v2_fields_new()
    test_v1_v2_coexist()
    test_agent_response_v2()
    test_ui_reads_only_v1()
    test_ui_reads_only_v2()
    test_multi_q_expander_protocol()

    print(f"\n{'=' * 40}")
    print(f"协议兼容性测试：{passed} 通过，{failed} 失败")
    print(f"{'=' * 40}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
