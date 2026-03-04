"""Phase 4 测试：任务状态管理验证。

验证 task_id 生成、状态流转、耗时记录。

用法：
    python tests/test_task_manager.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.task_manager import TaskManager, Task

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


def test_create_task():
    """创建任务，验证初始状态。"""
    print("[1] 创建任务")
    tm = TaskManager()
    task = tm.create_task(agent_id="multi_q_expander", params={"expand_count": 3}, input_rows=10)

    check("task_id 非空", bool(task.task_id))
    check("task_id 长度 12", len(task.task_id) == 12)
    check("status 为 pending", task.status == "pending")
    check("agent_id 正确", task.agent_id == "multi_q_expander")
    check("input_rows 正确", task.input_rows == 10)
    check("started_at 为 None", task.started_at is None)
    check("ended_at 为 None", task.ended_at is None)
    check("params_snapshot 保留", task.params_snapshot.get("expand_count") == 3)


def test_params_sanitization():
    """参数脱敏：以 _ 开头的参数不被记录。"""
    print("\n[2] 参数脱敏")
    tm = TaskManager()
    task = tm.create_task(
        agent_id="test",
        params={"expand_count": 3, "_api_key": "sk-secret", "_model": "gpt-4"},
    )
    check("_api_key 未记录", "_api_key" not in task.params_snapshot)
    check("_model 未记录", "_model" not in task.params_snapshot)
    check("expand_count 保留", "expand_count" in task.params_snapshot)


def test_start_task():
    """启动任务，验证状态变更。"""
    print("\n[3] 启动任务")
    tm = TaskManager()
    task = tm.create_task(agent_id="test")
    tm.start_task(task.task_id)

    check("status 为 running", task.status == "running")
    check("started_at 非 None", task.started_at is not None)
    check("ended_at 仍为 None", task.ended_at is None)


def test_complete_task():
    """任务成功完成。"""
    print("\n[4] 完成任务")
    tm = TaskManager()
    task = tm.create_task(agent_id="test")
    tm.start_task(task.task_id)
    time.sleep(0.05)
    tm.complete_task(task.task_id)

    check("status 为 success", task.status == "success")
    check("ended_at 非 None", task.ended_at is not None)
    check("duration > 0", task.duration_seconds is not None and task.duration_seconds > 0)
    check("error_message 为 None", task.error_message is None)


def test_fail_task():
    """任务失败。"""
    print("\n[5] 失败任务")
    tm = TaskManager()
    task = tm.create_task(agent_id="test")
    tm.start_task(task.task_id)
    time.sleep(0.02)
    tm.fail_task(task.task_id, "模型调用超时")

    check("status 为 failed", task.status == "failed")
    check("ended_at 非 None", task.ended_at is not None)
    check("duration > 0", task.duration_seconds is not None and task.duration_seconds > 0)
    check("error_message 正确", task.error_message == "模型调用超时")


def test_unique_task_ids():
    """并发创建多个任务，task_id 唯一。"""
    print("\n[6] task_id 唯一性")
    tm = TaskManager()
    ids = set()
    for _ in range(100):
        task = tm.create_task(agent_id="test")
        ids.add(task.task_id)

    check("100 个 task_id 全部唯一", len(ids) == 100)


def test_get_and_list():
    """查询和列举任务。"""
    print("\n[7] 查询与列举")
    tm = TaskManager()
    t1 = tm.create_task(agent_id="a1")
    t2 = tm.create_task(agent_id="a2")

    check("get 找到 t1", tm.get_task(t1.task_id) is t1)
    check("get 找到 t2", tm.get_task(t2.task_id) is t2)
    check("get 不存在返回 None", tm.get_task("nonexistent") is None)
    check("list 长度为 2", len(tm.list_tasks()) == 2)


def test_to_dict():
    """序列化为字典。"""
    print("\n[8] to_dict")
    tm = TaskManager()
    task = tm.create_task(agent_id="test", input_rows=5)
    tm.start_task(task.task_id)
    tm.complete_task(task.task_id)

    d = task.to_dict()
    check("task_id 存在", "task_id" in d)
    check("agent_id 存在", d["agent_id"] == "test")
    check("status 存在", d["status"] == "success")
    check("input_rows 存在", d["input_rows"] == 5)
    check("duration_seconds 存在", d["duration_seconds"] is not None)


def test_full_lifecycle():
    """完整生命周期：pending -> running -> success。"""
    print("\n[9] 完整生命周期")
    tm = TaskManager()
    task = tm.create_task(agent_id="multi_q_expander", params={"count": 5}, input_rows=10)
    check("初始 pending", task.status == "pending")

    tm.start_task(task.task_id)
    check("running", task.status == "running")
    check("started_at 有值", task.started_at is not None)

    time.sleep(0.02)
    tm.complete_task(task.task_id)
    check("success", task.status == "success")
    check("ended_at 有值", task.ended_at is not None)
    check("duration 有值", task.duration_seconds is not None)


def main():
    test_create_task()
    test_params_sanitization()
    test_start_task()
    test_complete_task()
    test_fail_task()
    test_unique_task_ids()
    test_get_and_list()
    test_to_dict()
    test_full_lifecycle()

    print(f"\n{'=' * 40}")
    print(f"任务管理测试：{passed} 通过，{failed} 失败")
    print(f"{'=' * 40}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
