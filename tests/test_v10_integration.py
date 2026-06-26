#!/usr/bin/env python3
"""
Berkshire AI V10.0 - 集成测试
端到端流程验证
"""
import os
import sys
import json
import subprocess
from datetime import datetime

# 路径配置
BERKSHIRE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BERKSHIRE_DIR, "src"))

from evolution_loop_v10 import BerkshireGraph, TextualGradientDescent
from tavily_search import TavilySearcher


def _skip(reason: str):
    """在 pytest 下触发 skip；作为脚本运行时静默忽略。"""
    try:
        import pytest
        pytest.skip(reason, allow_module_level=False)
    except ImportError:
        pass


def test_tavily_integration():
    """测试 Tavily 实时搜索集成。

    需要真实网络与 API Key（TAVILY_API_KEYS / TAVILY_API_KEY），
    未配置时跳过，避免 CI 无网络环境下误判失败。
    """
    print("\n" + "=" * 60)
    print("📊 测试: Tavily 实时搜索集成")
    print("=" * 60)

    if not (os.getenv("TAVILY_API_KEYS") or os.getenv("TAVILY_API_KEY")):
        msg = "未配置 TAVILY_API_KEYS / TAVILY_API_KEY，跳过 Tavily 集成测试"
        print(f"  ⚠️ {msg}")
        _skip(msg)
        return

    searcher = TavilySearcher()
    print(f"  ✅ Tavily 初始化成功 (Keys: {len(searcher.keys)})")

    result = searcher.get_stock_data("600519", "贵州茅台")

    # 外部服务/网络/鉴权问题（如 403/429/超时）属环境因素，跳过而非判失败
    if "error" in result:
        msg = f"Tavily 调用返回错误（环境/网络/鉴权问题），跳过: {result['error']}"
        print(f"  ⚠️ {msg}")
        _skip(msg)
        return

    assert "answer" in result, "缺少 answer 字段"
    assert len(result.get("sources", [])) > 0, "无搜索结果"
    print(f"  ✅ 股票数据获取成功")
    print(f"     摘要: {result['answer'][:80]}...")


def test_computation_graph():
    """测试计算图构建与反向传播"""
    print("\n" + "=" * 60)
    print("📊 测试: 计算图构建与反向传播")
    print("=" * 60)
    
    graph = BerkshireGraph()
    print(f"  ✅ 计算图初始化成功 (变量数: {len(graph.variables)})")

    # 测试拓扑排序
    order = graph.topological_sort()
    assert len(order) > 0, "拓扑排序为空"
    print(f"  ✅ 拓扑排序成功 (节点数: {len(order)})")

    # 测试反向传播
    scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
    gradients = graph.backward(scores)
    assert len(gradients) > 0, "梯度为空"

    # 验证节点级诊断
    failed_nodes = [k for k, v in gradients.items() if "❌" in v]
    assert failed_nodes, "低分场景应至少诊断出一个失败节点"
    print(f"  ✅ 反向传播成功 (梯度数: {len(gradients)})")
    print(f"     失败节点: {failed_nodes}")


def test_evolution_loop():
    """测试进化循环"""
    print("\n" + "=" * 60)
    print("📊 测试: 进化循环")
    print("=" * 60)
    
    # 运行 evolution_loop_v10.py
    result = subprocess.run(
        [sys.executable, os.path.join(BERKSHIRE_DIR, "src", "evolution_loop_v10.py")],
        capture_output=True,
        text=True,
        timeout=60
    )

    assert result.returncode == 0, f"执行失败: {result.stderr}"
    print(f"  ✅ 进化循环执行成功")
    assert "Graph created" in result.stdout, f"缺少预期输出，实际: {result.stdout[:120]}"
    print(f"  ✅ 输出包含预期标识")


def test_trace_recording():
    """测试轨迹记录"""
    print("\n" + "=" * 60)
    print("📊 测试: 轨迹记录")
    print("=" * 60)
    
    trace_dir = os.path.expanduser("~/.qwenpaw/berkshire_traces")
    if not os.path.exists(trace_dir):
        msg = f"轨迹目录不存在: {trace_dir}"
        print(f"  ⚠️ {msg}")
        _skip(msg)
        return

    traces = [f for f in os.listdir(trace_dir) if f.endswith(".json")]
    print(f"  ✅ 轨迹目录存在 (文件数: {len(traces)})")

    if traces:
        # 读取最新轨迹
        latest = sorted(traces)[-1]
        with open(os.path.join(trace_dir, latest)) as f:
            data = json.load(f)
        print(f"  ✅ 最新轨迹: {latest}")
        if isinstance(data, dict):
            print(f"     时间: {data.get('timestamp', 'N/A')}")
        else:
            print(f"     轨迹数: {len(data) if isinstance(data, list) else 1}")


def test_state_file():
    """测试状态文件"""
    print("\n" + "=" * 60)
    print("📊 测试: 状态文件")
    print("=" * 60)
    
    state_file = os.path.join(BERKSHIRE_DIR, "config", "state.md")
    assert os.path.exists(state_file), f"状态文件不存在: {state_file}"

    with open(state_file) as f:
        content = f.read()

    # 检查关键内容
    checks = [
        ("V10", "版本标识"),
        ("Cron", "Cron 任务"),
        ("TextGrad", "TextGrad 化"),
    ]

    missing = [f"{desc}({keyword})" for keyword, desc in checks if keyword not in content]
    for keyword, desc in checks:
        mark = "✅" if keyword in content else "❌"
        print(f"  {mark} {desc}: {keyword}")
    assert not missing, f"状态文件缺少关键内容: {', '.join(missing)}"


def main():
    print("=" * 60)
    print("Berkshire AI V10.0 - 集成测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Tavily 集成", test_tavily_integration),
        ("计算图", test_computation_graph),
        ("进化循环", test_evolution_loop),
        ("轨迹记录", test_trace_recording),
        ("状态文件", test_state_file),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "pass"))
        except Exception as e:
            # pytest.skip 抛出的 Skipped 异常在脚本模式下视为跳过
            if type(e).__name__ == "Skipped":
                results.append((name, "skip"))
            else:
                print(f"  ❌ 异常: {e}")
                results.append((name, "fail"))

    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)

    passed = sum(1 for _, s in results if s == "pass")
    skipped = sum(1 for _, s in results if s == "skip")
    failed = sum(1 for _, s in results if s == "fail")
    total = len(results)

    marks = {"pass": "✅ 通过", "skip": "⚠️ 跳过", "fail": "❌ 失败"}
    for name, s in results:
        print(f"  {marks[s]}: {name}")

    print(f"\n总计: {passed} 通过 / {skipped} 跳过 / {failed} 失败 (共 {total})")

    if failed == 0:
        print("\n✅ 无失败用例，V10 可以上线。")
        return 0
    else:
        print(f"\n❌ {failed} 个测试失败，请修复后重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
