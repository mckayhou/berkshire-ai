#!/usr/bin/env python3
"""
Berkshire AI V10.0 - TextGrad 化进化引擎 (modular)

Thin entrypoint. Core logic in graph.py and optimizer.py.

See update-platforms.sh for deployment to OpenClaw/QwenPaw.
"""

# Absolute imports for compatibility (sys.path insert to src/ in tests)
try:
    from graph import BerkshireGraph, Variable, Gradient, Master, MASTERS
    from optimizer import TextualGradientDescent
except ImportError:
    from .graph import BerkshireGraph, Variable, Gradient, Master, MASTERS
    from .optimizer import TextualGradientDescent

__all__ = [
    "BerkshireGraph",
    "Variable",
    "Gradient",
    "Master",
    "MASTERS",
    "TextualGradientDescent",
    "run_example",
]


def run_example():
    """Simple runner for the engine."""
    graph = BerkshireGraph()
    print("Graph created with", len(graph.variables), "nodes")
    scores = {"duan": 0.92, "buffett": 0.68, "munger": 0.85, "lilu": 0.55}
    gradients = graph.backward(scores)
    optimizer = TextualGradientDescent(graph)
    updates = optimizer.step(gradients)
    print("Updates needed:", len(updates))
    return graph, gradients, updates


if __name__ == "__main__":
    run_example()
