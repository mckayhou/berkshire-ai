# Berkshire AI V10.0 - TextGrad 化设计

> 基于 TextGrad (Nature 2025) 的自动微分思想，重构 Berkshire 进化机制

## 📖 TextGrad 核心概念

| 概念 | 定义 | Berkshire 映射 |
|:-----|:-----|:---------------|
| **计算图** | 变量 + 依赖关系的有向图 | 四大师分析流程 |
| **变量** | 可优化的节点 (Prompt/代码/分子) | 大师 Prompt + 模型 + Tavily Query |
| **文本梯度** | LLM 生成的诊断+修改建议 | 节点级失败分析 |
| **反向传播** | 从输出向输入传播梯度 | 从最终评分向各大师回传诊断 |
| **优化器** | 根据梯度更新变量 | 针对性修改失败节点的 Prompt/模型 |

## 🎯 Berkshire 计算图设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Berkshire Computation Graph                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 0: 输入层                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ ticker      │  │ tavily_query│  │ date_anchor │                 │
│  │ (股票代码)   │  │ (搜索策略)   │  │ (日期锚定)   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│  Layer 1: 数据获取层                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    tavily_search()                           │   │
│  │  → stock_data + financial_metrics + industry_news           │   │
│  └────────────────────────────┬────────────────────────────────┘   │
│                               │                                     │
│          ┌────────────────────┼────────────────────┐               │
│          ▼                    ▼                    ▼               │
│  Layer 2: 四大师分析层                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │ 段永平       │  │ 巴菲特       │  │ 芒格         │  │ 李录     │  │
│  │ (生意本质)   │  │ (护城河估值) │  │ (逆向风险)   │  │ (文明趋势)│  │
│  │             │  │             │  │             │  │         │  │
│  │ Variable:   │  │ Variable:   │  │ Variable:   │  │Variable:│  │
│  │ duan_prompt │  │ buffett_    │  │ munger_     │  │ lilu_   │  │
│  │ duan_model  │  │ prompt      │  │ prompt      │  │ prompt  │  │
│  │             │  │ buffett_    │  │ munger_     │  │ lilu_   │  │
│  │             │  │ model       │  │ model       │  │ model   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘  │
│         │                │                │               │        │
│         └────────────────┼────────────────┴───────────────┘        │
│                          ▼                                          │
│  Layer 3: 综合评估层                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    financial_rigor.py                        │   │
│  │  → 市值验证 + 估值验证 + 交叉验证                             │   │
│  └────────────────────────────┬────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│  Layer 4: 输出层                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    final_report                              │   │
│  │  → 平均评分 + 投资建议 + 风险提示                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🔍 节点级诊断机制

### 当前问题 (V9.3)
```
失败案例: 腾讯控股分析评分 0.75 (低于目标 0.85)
反思报告: "整体评分偏低，需要改进 Prompt"
问题: 不知道具体哪个大师/哪个环节出了问题
```

### TextGrad 化后 (V10.0)
```
失败案例: 腾讯控股分析评分 0.75
反向传播诊断:
  - 段永平 (0.92): ✅ 正常
  - 巴菲特 (0.68): ❌ 估值偏高，PE 计算错误
    → 梯度: "buffett_prompt 缺少 PE 行业对比约束"
  - 芒格 (0.85): ✅ 正常
  - 李录 (0.55): ❌ 风险评估过于乐观
    → 梯度: "lilu_prompt 缺少监管风险分析"
优化动作:
  - 修改 buffett_prompt: 添加 PE 行业对比约束
  - 修改 lilu_prompt: 添加监管风险清单
```

## 📐 实现方案

### 1. 计算图定义 (Python)
```python
class BerkshireGraph:
    def __init__(self):
        # Layer 0: 输入变量
        self.variables = {
            "ticker": Variable("ticker", type="input"),
            "tavily_query": Variable("tavily_query", type="input"),
            "date_anchor": Variable("date_anchor", type="input"),
            
            # Layer 2: 四大师变量
            "duan_prompt": Variable("duan_prompt", type="prompt", role="段永平"),
            "duan_model": Variable("duan_model", type="model", role="段永平"),
            "buffett_prompt": Variable("buffett_prompt", type="prompt", role="巴菲特"),
            "buffett_model": Variable("buffett_model", type="model", role="巴菲特"),
            "munger_prompt": Variable("munger_prompt", type="prompt", role="芒格"),
            "munger_model": Variable("munger_model", type="model", role="芒格"),
            "lilu_prompt": Variable("lilu_prompt", type="prompt", role="李录"),
            "lilu_model": Variable("lilu_model", type="model", role="李录"),
        }
        
        # 依赖关系 (edges)
        self.edges = [
            # Layer 0 → Layer 1
            ("ticker", "tavily_search"),
            ("tavily_query", "tavily_search"),
            ("date_anchor", "tavily_search"),
            
            # Layer 1 → Layer 2
            ("tavily_search", "duan_analysis"),
            ("tavily_search", "buffett_analysis"),
            ("tavily_search", "munger_analysis"),
            ("tavily_search", "lilu_analysis"),
            
            # Layer 2 变量 → Layer 2 分析
            ("duan_prompt", "duan_analysis"),
            ("duan_model", "duan_analysis"),
            ("buffett_prompt", "buffett_analysis"),
            ("buffett_model", "buffett_analysis"),
            ("munger_prompt", "munger_analysis"),
            ("munger_model", "munger_analysis"),
            ("lilu_prompt", "lilu_analysis"),
            ("lilu_model", "lilu_analysis"),
            
            # Layer 2 → Layer 3
            ("duan_analysis", "financial_rigor"),
            ("buffett_analysis", "financial_rigor"),
            ("munger_analysis", "financial_rigor"),
            ("lilu_analysis", "financial_rigor"),
            
            # Layer 3 → Layer 4
            ("financial_rigor", "final_report"),
        ]
    
    def backward(self, failure_trace: dict) -> dict:
        """
        沿计算图反向传播文本梯度
        
        Args:
            failure_trace: 包含最终评分和各大师评分的字典
        
        Returns:
            gradients: 每个变量的文本梯度 (诊断+修改建议)
        """
        gradients = {}
        
        # 从输出层向输入层反向遍历
        for node in reversed(topological_sort(self.edges)):
            if node in ["final_report", "financial_rigor"]:
                # 输出层：根据最终评分生成梯度
                gradients[node] = self.compute_output_gradient(failure_trace)
            elif node.endswith("_analysis"):
                # 四大师分析层：根据各大师评分生成梯度
                role = node.split("_")[0]
                score = failure_trace.get(f"{role}_score", 0)
                gradients[node] = self.compute_master_gradient(role, score)
            elif node in self.variables:
                # 变量层：根据下游梯度生成变量梯度
                downstream_grad = gradients.get(self.get_successor(node))
                gradients[node] = self.compute_variable_gradient(
                    node, downstream_grad
                )
        
        return gradients
    
    def compute_master_gradient(self, role: str, score: float) -> str:
        """为四大师分析生成文本梯度"""
        if score >= 0.85:
            return f"✅ {role} 分析质量良好 (评分 {score})"
        
        issues = []
        if score < 0.70:
            issues.append(f"评分过低 ({score})，需要重点改进")
        
        # 根据角色特性生成针对性诊断
        if role == "巴菲特":
            if "估值" not in self.last_output:
                issues.append("缺少估值分析 (PE/PB/DCF)")
            if "护城河" not in self.last_output:
                issues.append("缺少护城河评估")
        elif role == "芒格":
            if "风险" not in self.last_output:
                issues.append("缺少风险分析")
            if "失败" not in self.last_output:
                issues.append("缺少逆向思考")
        # ... 其他角色类似
        
        return f"❌ {role} 分析存在问题:\n" + "\n".join(issues)
```

### 2. 节点级诊断 (LLM 调用)
```python
def compute_text_gradient(node: Variable, downstream_feedback: str) -> str:
    """
    使用 LLM 为变量生成文本梯度
    
    类比 TextGrad 的 ∇_LLM 算子
    """
    prompt = f"""
    你是一个 AI 系统优化专家。以下是某个分析节点的下游反馈：
    
    节点: {node.name}
    角色: {node.role or 'N/A'}
    当前值: {node.value}
    
    下游反馈:
    {downstream_feedback}
    
    请分析：
    1. 这个节点的哪些部分导致了下游问题？
    2. 应该如何修改这个节点以改进输出？
    
    输出格式：
    **诊断**: [具体问题]
    **修改建议**: [具体修改]
    """
    
    return llm.call(prompt)
```

### 3. 优化器 (Textual Gradient Descent)
```python
class TextualGradientDescent:
    def __init__(self, variables: list, lr: float = 1.0):
        self.variables = variables
        self.lr = lr
    
    def step(self, gradients: dict):
        """根据梯度更新变量"""
        for var in self.variables:
            grad = gradients.get(var.name)
            if grad and "❌" in grad:
                # 有问题，需要修改
                new_value = self.apply_gradient(var, grad)
                var.update(new_value)
                self.log_update(var, grad, new_value)
    
    def apply_gradient(self, var: Variable, gradient: str) -> str:
        """应用梯度到变量"""
        prompt = f"""
        当前变量值:
        {var.value}
        
        需要改进的方向:
        {gradient}
        
        请根据改进方向修改变量值，保持核心结构不变。
        """
        return llm.call(prompt)
```

## 📊 预期收益

| 指标 | V9.3 (当前) | V10.0 (预期) | 提升 |
|:-----|:------------|:-------------|:-----|
| 诊断精度 | 整体评分 | 节点级定位 | ⭐⭐⭐ |
| 优化效率 | 全局修改 | 针对性修改 | ⭐⭐⭐ |
| 进化速度 | 慢 (试错) | 快 (定向) | ⭐⭐ |
| 可解释性 | 低 | 高 (梯度可视化) | ⭐⭐⭐ |

## 🚀 实施计划

### Phase 1: 计算图定义 (Week 1)
- [ ] 实现 `BerkshireGraph` 类
- [ ] 定义变量和依赖关系
- [ ] 实现拓扑排序

### Phase 2: 反向传播 (Week 2)
- [ ] 实现 `backward()` 方法
- [ ] 实现节点级梯度计算
- [ ] 集成 LLM 诊断

### Phase 3: 优化器 (Week 3)
- [ ] 实现 `TextualGradientDescent`
- [ ] 实现变量更新逻辑
- [ ] 添加更新日志

### Phase 4: 集成测试 (Week 4)
- [ ] 使用历史轨迹测试
- [ ] 对比 V9.3 vs V10.0
- [ ] 文档更新

## 📝 关键决策

1. **是否完全重写进化机制？**
   - ❌ 否。保留 V9.3 的轨迹记录，在其基础上叠加计算图
   
2. **是否需要额外的 LLM 调用？**
   - ✅ 是。每个节点需要一次 LLM 调用生成梯度
   - 成本: 约 10-15 次额外调用/次投研
   - 收益: 精准定位问题，减少无效迭代

3. **如何验证效果？**
   - 使用 24 条历史轨迹回测
   - 对比诊断准确率
   - 对比优化后的评分提升

---

**下一步**: 实现 `BerkshireGraph` 类并集成到 `evolution_loop_v10.py`
