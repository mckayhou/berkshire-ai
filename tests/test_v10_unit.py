#!/usr/bin/env python3
"""
Berkshire AI V10.0 单元测试
测试 TextGrad 计算图核心功能
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from evolution_loop_v10 import (
    MASTERS,
    BerkshireGraph,
    Gradient,
    TextualGradientDescent,
)


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


def test_masters_single_source():
    """MASTERS 是唯一来源：每位大师都派生出 prompt/model/analysis 三个节点"""
    graph = BerkshireGraph()
    assert len(MASTERS) >= 4, "至少应有四位大师"
    for m in MASTERS:
        for node in (
            graph.prompt_node(m.prefix),
            graph.model_node(m.prefix),
            graph.analysis_node(m.prefix),
        ):
            assert node in graph.variables, f"缺少节点 {node}"
        # role 名称应一致地挂在变量上
        assert graph.variables[graph.analysis_node(m.prefix)].role == m.name
    print("✅ MASTERS 单一来源测试通过")


def test_gradient_is_structured():
    """backward 返回结构化 Gradient；控制流应读 ok 而非解析 emoji"""
    graph = BerkshireGraph()
    scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
    gradients = graph.backward(scores)

    # 类型契约
    for g in gradients.values():
        assert isinstance(g, Gradient), "梯度应为 Gradient 实例"

    # 高分达标：ok=True 且无 issues
    duan = gradients["duan_analysis"]
    assert duan.ok is True and not duan.issues

    # 低分未达标：ok=False 且有结构化 issues
    lilu = gradients["lilu_analysis"]
    assert lilu.ok is False and len(lilu.issues) > 0

    # 展示兼容性仍可用，但不应用于控制流
    assert "❌" in lilu  # __contains__ 委托到 text
    print("✅ 结构化梯度测试通过")


def test_optimizer_reads_ok_field():
    """全部达标 → 零更新；存在未达标 → 更新项带结构化 issues"""
    graph = BerkshireGraph()
    optimizer = TextualGradientDescent(graph)

    # 全部达标
    all_pass = {m.prefix: 0.95 for m in MASTERS}
    assert optimizer.step(graph.backward(all_pass)) == [], "全达标不应产生更新"

    # 部分未达标
    mixed = {m.prefix: 0.60 for m in MASTERS}
    updates = optimizer.step(graph.backward(mixed))
    assert len(updates) > 0, "未达标应产生更新"
    assert all("issues" in u for u in updates), "更新项应携带结构化 issues"
    print("✅ 优化器结构化契约测试通过")


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
    test_masters_single_source()
    test_gradient_is_structured()
    test_optimizer_reads_ok_field()
    
    print()
    print("=" * 70)
    print("✅ 所有单元测试通过 (8/8)")
    print("=" * 70)
