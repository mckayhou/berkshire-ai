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


def test_tavily_integration():
    """测试 Tavily 实时搜索集成"""
    print("\n" + "=" * 60)
    print("📊 测试: Tavily 实时搜索集成")
    print("=" * 60)
    
    # 设置环境变量
    os.environ["TAVILY_API_KEYS"] = "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,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"
    
    try:
        searcher = TavilySearcher()
        print(f"  ✅ Tavily 初始化成功 (Keys: {len(searcher.keys)})")
        
        # 测试股票数据获取
        result = searcher.get_stock_data("600519", "贵州茅台")
        assert "answer" in result, "缺少 answer 字段"
        assert len(result.get("sources", [])) > 0, "无搜索结果"
        print(f"  ✅ 股票数据获取成功")
        print(f"     摘要: {result['answer'][:80]}...")
        
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_computation_graph():
    """测试计算图构建与反向传播"""
    print("\n" + "=" * 60)
    print("📊 测试: 计算图构建与反向传播")
    print("=" * 60)
    
    try:
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
        print(f"  ✅ 反向传播成功 (梯度数: {len(gradients)})")
        print(f"     失败节点: {failed_nodes}")
        
        return True
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_evolution_loop():
    """测试进化循环"""
    print("\n" + "=" * 60)
    print("📊 测试: 进化循环")
    print("=" * 60)
    
    try:
        # 运行 evolution_loop_v10.py
        result = subprocess.run(
            [sys.executable, os.path.join(BERKSHIRE_DIR, "src", "evolution_loop_v10.py")],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"  ✅ 进化循环执行成功")
            # 检查输出
            if "V10.0" in result.stdout:
                print(f"  ✅ 版本标识正确 (V10.0)")
            return True
        else:
            print(f"  ❌ 执行失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ 超时")
        return False
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_trace_recording():
    """测试轨迹记录"""
    print("\n" + "=" * 60)
    print("📊 测试: 轨迹记录")
    print("=" * 60)
    
    trace_dir = os.path.expanduser("~/.qwenpaw/berkshire_traces")
    if not os.path.exists(trace_dir):
        print(f"  ⚠️ 轨迹目录不存在: {trace_dir}")
        return True
    
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
    
    return True


def test_state_file():
    """测试状态文件"""
    print("\n" + "=" * 60)
    print("📊 测试: 状态文件")
    print("=" * 60)
    
    state_file = os.path.join(BERKSHIRE_DIR, "config", "state.md")
    if not os.path.exists(state_file):
        print(f"  ❌ 状态文件不存在: {state_file}")
        return False
    
    with open(state_file) as f:
        content = f.read()
    
    # 检查关键内容
    checks = [
        ("V10.0", "版本标识"),
        ("Cron", "Cron 任务"),
        ("TextGrad", "TextGrad 化"),
    ]
    
    all_pass = True
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ {desc}: {keyword}")
        else:
            print(f"  ❌ {desc}: {keyword} 缺失")
            all_pass = False
    
    return all_pass


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
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = "✅ 通过" if p else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✅ 所有测试通过！V10.0 可以上线。")
        return 0
    else:
        print(f"\n❌ {total - passed} 个测试失败，请修复后重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
