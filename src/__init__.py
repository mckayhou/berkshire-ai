"""
Berkshire AI V10 engine package.

Exports the main classes for TextGrad-based 4-masters analysis.
"""

from .graph import BerkshireGraph, Variable
from .optimizer import TextualGradientDescent

__all__ = ["BerkshireGraph", "Variable", "TextualGradientDescent"]
