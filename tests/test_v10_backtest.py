#!/usr/bin/env python3
"""
Berkshire AI V10.0 - 回测验证
使用历史轨迹数据验证 TextGrad 诊断效果
"""
import os
import sys
import json
import glob
from collections import defaultdict
from datetime import datetime

# 路径配置
BERKSHIRE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BERKSHIRE_DIR, "src"))

from evolution_loop_v10 import BerkshireGraph


def load_traces(trace_dir: str) -> list:
    """加载所有轨迹文件"""
    traces = []
    for f in glob.glob(os.path.join(trace_dir, "*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)
                data["_file"] = os.path.basename(f)
                traces.append(data)
        except:
            pass
    return traces


def extract_scores(trace: dict) -> dict:
    """从轨迹中提取评分"""
    scores = {}
    
    role = trace.get("agent_role", "")
    phase = trace.get("phase", "")
    
    role_map = {
        "段永平": "duan",
        "巴菲特": "buffett",
        "芒格": "munger",
        "李录": "lilu",
        "hunter": "duan",
        "maker": "buffett",
        "checker": "munger",
        "pm": "lilu",
    }
    
    key = role if role in role_map.values() else role_map.get(role, role_map.get(phase))
    score = trace.get("score", 0)
    
    if key and score > 0:
        scores[key] = score
    
    return scores


def run_backtest():
    """执行回测"""
    print("=" * 60)
    print("Berkshire V10.0 - 回测验证")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 加载轨迹
    trace_dir = os.path.expanduser("~/.qwenpaw/berkshire_traces")
    if not os.path.exists(trace_dir):
        print(f"❌ 轨迹目录不存在: {trace_dir}")
        return False
    
    traces = load_traces(trace_dir)
    print(f"\n📊 加载轨迹: {len(traces)} 条")
    
    if not traces:
        print("⚠️ 无轨迹数据，跳过回测")
        return True
    
    # 按任务分组
    tasks = defaultdict(dict)
    for t in traces:
        filename = t.get("_file", "")
        ticker = filename.split("_")[0] if "_" in filename else "unknown"
        
        scores = extract_scores(t)
        for role, score in scores.items():
            tasks[ticker][role] = {
                "score": score,
                "trace": t,
            }
    
    print(f"📊 任务数: {len(tasks)}")
    
    # 创建计算图
    graph = BerkshireGraph()
    
    # 回测每个任务
    results = []
    for ticker, roles in tasks.items():
        if len(roles) < 2:
            continue
        
        scores = {role: data["score"] for role, data in roles.items()}
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        
        # V10.0 反向传播
        gradients = graph.backward(scores)
        
        issues_found = sum(1 for g in gradients.values() if not g.ok)
        prompts_to_fix = sum(1 for k, g in gradients.items() if k.endswith("_prompt") and not g.ok)
        
        result = {
            "ticker": ticker,
            "scores": scores,
            "avg_score": avg_score,
            "issues_found": issues_found,
            "prompts_to_fix": prompts_to_fix,
        }
        results.append(result)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("📊 回测结果")
    print("=" * 60)
    
    for r in results:
        print(f"\n📈 {r['ticker']}")
        print(f"  评分: {r['scores']}")
        print(f"  平均: {r['avg_score']:.3f}")
        print(f"  V9.3 诊断: 整体评分 {r['avg_score']:.3f} {'✅' if r['avg_score'] >= 0.85 else '❌'}")
        print(f"  V10.0 诊断:")
        print(f"    - 发现问题数: {r['issues_found']}")
        print(f"    - 需修改 Prompt: {r['prompts_to_fix']}")
    
    # 统计汇总
    print("\n" + "=" * 60)
    print("📊 统计汇总")
    print("=" * 60)
    
    total_tasks = len(results)
    tasks_with_issues = sum(1 for r in results if r['avg_score'] < 0.85)
    tasks_with_node_diagnosis = sum(1 for r in results if r['issues_found'] > 0)
    
    print(f"总任务数: {total_tasks}")
    print(f"低于目标 (0.85): {tasks_with_issues}")
    print(f"V10.0 节点级诊断: {tasks_with_node_diagnosis}")
    
    if tasks_with_issues > 0:
        precision = tasks_with_node_diagnosis / tasks_with_issues * 100
        print(f"诊断覆盖率: {precision:.1f}%")
        
        if precision >= 90:
            print("\n✅ 诊断覆盖率 ≥ 90%，V10.0 可以上线。")
            return True
        else:
            print(f"\n❌ 诊断覆盖率 {precision:.1f}% < 90%，需要优化。")
            return False
    else:
        print("\n✅ 所有任务达标，无需诊断。")
        return True


if __name__ == "__main__":
    success = run_backtest()
    sys.exit(0 if success else 1)
