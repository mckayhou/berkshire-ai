#!/usr/bin/env python3
"""
Berkshire AI V10.0 单元测试
测试 TextGrad 计算图核心功能
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from evolution_loop_v10 import BerkshireGraph, TextualGradientDescent


def test_graph_initialization():
    """测试计算图初始化"""
    graph = BerkshireGraph()
    assert len(graph.variables) > 0, "变量数应大于0"
    assert len(graph.edges) > 0, "边数应大于0"
    print("✅ 计算图初始化测试通过")


def test_topological_sort():
    """测试拓扑排序"""
    graph = BerkshireGraph()
    order = graph.topological_sort()
    assert len(order) > 0, "拓扑排序结果不应为空"
    
    # 验证输入节点在前
    input_nodes = ['ticker', 'tavily_query', 'date_anchor']
    for node in input_nodes:
        if node in order:
            idx = order.index(node)
            # 输入节点应该在前面
            assert idx < len(order) // 2, f"{node} 应该在排序前半部分"
    
    print("✅ 拓扑排序测试通过")


def test_backward_propagation():
    """测试反向传播"""
    graph = BerkshireGraph()
    
    # 模拟失败案例
    scores = {
        'duan': 0.92,
        'buffett': 0.68,  # 偏低
        'munger': 0.85,
        'lilu': 0.55,     # 过低
    }
    
    gradients = graph.backward(scores)
    assert len(gradients) > 0, "梯度数应大于0"
    
    # 验证低分大师有梯度（读取结构化 ok 字段，而非解析 emoji 文本）
    buffett_grad = gradients['buffett_analysis']
    lilu_grad = gradients['lilu_analysis']
    assert (not buffett_grad.ok) or (not lilu_grad.ok), "低分大师应被标记为未达标"
    
    print("✅ 反向传播测试通过")


def test_optimizer():
    """测试优化器"""
    graph = BerkshireGraph()
    scores = {'duan': 0.60, 'buffett': 0.70, 'munger': 0.80, 'lilu': 0.90}
    gradients = graph.backward(scores)
    
    optimizer = TextualGradientDescent(graph)
    updates = optimizer.step(gradients)
    
    assert len(updates) > 0, "应有更新操作"
    print("✅ 优化器测试通过")


def test_visualization():
    """测试可视化"""
    graph = BerkshireGraph()
    viz = graph.visualize()
    
    assert 'Layer 0' in viz, "应包含 Layer 0"
    assert 'ticker' in viz, "应包含 ticker 变量"
    print("✅ 可视化测试通过")


if __name__ == '__main__':
    print("=" * 70)
    print("Berkshire AI V10.0 单元测试")
    print("=" * 70)
    print()
    
    test_graph_initialization()
    test_topological_sort()
    test_backward_propagation()
    test_optimizer()
    test_visualization()
    
    print()
    print("=" * 70)
    print("✅ 所有单元测试通过 (5/5)")
    print("=" * 70)
