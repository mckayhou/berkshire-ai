"""Out-of-sample evaluation for mined formulas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data_engine import AshareDataEngine
from .decode import decode_formula
from .vm import FormulaVM


@dataclass
class OOSReport:
    formula: str
    test_start: str
    test_end: str
    ann_return: float
    ann_vol: float
    sharpe: float
    max_drawdown: float
    calmar: float
    total_return: float

    def as_text(self) -> str:
        lines = [
            "=" * 60,
            "OUT-OF-SAMPLE CHECK (Open-to-Open)",
            "=" * 60,
            f"Strategy Formula: {self.formula}",
            f"Test Period      : {self.test_start} ~ {self.test_end}",
            f"Ann. Return      : {self.ann_return:.2%}",
            f"Ann. Volatility  : {self.ann_vol:.2%}",
            f"Sharpe Ratio     : {self.sharpe:.2f}",
            f"Max Drawdown     : {self.max_drawdown:.2%}",
            f"Calmar Ratio     : {self.calmar:.2f}",
            f"Total Return     : {self.total_return:.2%}",
            "-" * 60,
        ]
        return "\n".join(lines)


def run_oos_check(
    engine: AshareDataEngine,
    formula_tokens: list[int] | None,
    *,
    cost_rate: float = 0.0005,
) -> OOSReport | None:
    if not formula_tokens:
        return None

    vm = FormulaVM(engine.feat_data)
    factor_all = vm.solve_one(formula_tokens)
    if factor_all is None:
        return None

    split = engine.split_idx
    dates = engine.dates
    test_factors = factor_all[split:].detach().cpu().numpy()
    test_ret = engine.target_oto_ret[split:].detach().cpu().numpy()

    signal = np.tanh(test_factors)
    position = np.sign(signal)
    turnover = np.abs(position - np.roll(position, 1))
    turnover[0] = 0.0
    daily_ret = position * test_ret - turnover * cost_rate

    equity = (1 + daily_ret).cumprod()
    total_ret = float(equity[-1] - 1) if len(equity) else 0.0
    n = max(len(equity), 1)
    ann_ret = float(equity[-1] ** (252 / n) - 1) if len(equity) else 0.0
    vol = float(np.std(daily_ret) * np.sqrt(252)) if len(daily_ret) else 0.0
    sharpe = float((ann_ret - 0.02) / (vol + 1e-6))
    dd = 1 - equity / np.maximum.accumulate(equity)
    max_dd = float(np.max(dd)) if len(dd) else 0.0
    calmar = float(ann_ret / (max_dd + 1e-6))

    test_start = str(dates[split]) if dates else ""
    test_end = str(dates[-1]) if dates else ""
    if len(test_start) == 8 and test_start.isdigit():
        test_start = f"{test_start[:4]}-{test_start[4:6]}-{test_start[6:8]}"
    if len(test_end) == 8 and test_end.isdigit():
        test_end = f"{test_end[:4]}-{test_end[4:6]}-{test_end[6:8]}"

    return OOSReport(
        formula=decode_formula(formula_tokens),
        test_start=test_start,
        test_end=test_end,
        ann_return=ann_ret,
        ann_vol=vol,
        sharpe=sharpe,
        max_drawdown=max_dd,
        calmar=calmar,
        total_return=total_ret,
    )
