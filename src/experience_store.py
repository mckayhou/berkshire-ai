#!/usr/bin/env python3
"""
结构化经验沉淀 + 可检索复用（RAG-lite）。

借鉴 [microsoft/RD-Agent] 的 knowledge_base + research RAG + CoSTEER knowledge
sampler：把 `realized_feedback` **已经算出、却用完即弃**的成败信号（alpha /
realized_base / 当时各大师信心）连同一句「教训」沉淀成**可检索经验**，在下一轮
prompt 改写时作为 few-shot 回灌——让系统从「每轮从零改 prompt」升级为「从过去
的错误里学习」。

工程约束（与本项目一致）
--------------------------------------------------
- 零新依赖：默认 `KeywordExperienceRetriever` 用**确定性关键词召回**，无需向量库；
  检索器是可注入接口（Protocol），将来可换 embedding 实现而不动调用方。
- JSONL 落盘，复用 `decision_log` 的落盘风格；路径可用 BERKSHIRE_EXPERIENCE_LOG 覆盖。
- 检索**绝不把异常抛到主链路**：失败/无命中一律返回 []，调用方据此降级回原行为。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, runtime_checkable

ENV_LOG_PATH = "BERKSHIRE_EXPERIENCE_LOG"
DEFAULT_LOG_PATH = os.path.join(os.path.expanduser("~"), ".berkshire", "experiences.jsonl")

# verdict 取值（控制流读字段，不解析展示文本）
VERDICT_CONFIRMED = "confirmed"
VERDICT_REFUTED = "refuted"
VERDICT_NEUTRAL = "neutral"


def default_log_path() -> str:
    """经验日志默认路径（环境变量可覆盖）。"""
    return os.environ.get(ENV_LOG_PATH, DEFAULT_LOG_PATH)


def classify_verdict(alpha: float, *, band: float = 0.0) -> str:
    """由超额收益 alpha 判定成败裁决（确定性，可单测）。

    - alpha >  band → confirmed（决策被市场证明正确）
    - alpha < -band → refuted（被证伪）
    - 否则           → neutral
    """
    if alpha > band:
        return VERDICT_CONFIRMED
    if alpha < -band:
        return VERDICT_REFUTED
    return VERDICT_NEUTRAL


@dataclass
class Experience:
    """一条可检索的历史成败经验（结构化，控制流读字段）。"""

    ticker: str
    date: str
    stances: Dict[str, float]          # 当时各大师信心 {prefix: 0~1}
    alpha: float                       # 已实现超额收益
    realized_base: float               # 收益锚定真相分 ∈ [0,1]
    verdict: str                       # confirmed / refuted / neutral
    lesson: str = ""                   # 自由文本教训（展示 + few-shot 用）
    sector: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    hypothesis_id: Optional[str] = None   # 衔接 hypothesis.py（经验可按假设聚合）
    run_id: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        self.ticker = str(self.ticker).strip().upper()
        if not self.ticker:
            raise ValueError("ticker 不能为空")
        self.alpha = float(self.alpha)
        self.realized_base = float(self.realized_base)
        if self.verdict not in (VERDICT_CONFIRMED, VERDICT_REFUTED, VERDICT_NEUTRAL):
            raise ValueError(f"非法 verdict: {self.verdict!r}")
        if self.sector is not None:
            self.sector = str(self.sector).strip().upper() or None
        self.tags = [str(t).strip().lower() for t in (self.tags or []) if str(t).strip()]
        self.stances = {str(k): float(v) for k, v in (self.stances or {}).items()}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Experience":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


def experience_from_stats(
    decision,
    stats,
    *,
    lesson: str = "",
    sector: Optional[str] = None,
    tags: Optional[List[str]] = None,
    hypothesis_id: Optional[str] = None,
    run_id: Optional[str] = None,
    band: float = 0.0,
) -> Experience:
    """把 `realized_feedback` 的结果（鸭子类型）转成可检索 Experience。

    decision 需含 `.ticker/.date/.scores`；stats 需含 `.alpha/.realized_base`
    （即 `realized_feedback.ReturnStats`）。不硬 import，避免引入循环依赖。
    """
    return Experience(
        ticker=decision.ticker,
        date=getattr(decision, "date", ""),
        stances=dict(getattr(decision, "scores", {}) or {}),
        alpha=float(stats.alpha),
        realized_base=float(stats.realized_base),
        verdict=classify_verdict(float(stats.alpha), band=band),
        lesson=lesson,
        sector=sector,
        tags=tags or [],
        hypothesis_id=hypothesis_id,
        run_id=run_id,
    )


class ExperienceStore:
    """JSONL 落盘的经验库（复用 decision_log 风格；路径可被环境变量覆盖）。"""

    def __init__(self, path: Optional[str] = None):
        self.path = path or default_log_path()

    def append(self, exp: Experience) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")
        return self.path

    def load(self) -> List[Experience]:
        if not os.path.exists(self.path):
            return []
        out: List[Experience] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Experience.from_dict(json.loads(line)))
                except (ValueError, TypeError):  # 单行损坏跳过，不崩
                    continue
        return out


@runtime_checkable
class ExperienceRetriever(Protocol):
    """可注入检索接口。失败/无命中返回 []，绝不抛到主链路。"""

    def retrieve(
        self,
        *,
        ticker: str,
        sector: Optional[str] = None,
        tags: Optional[List[str]] = None,
        k: int = 3,
    ) -> List[Experience]: ...


class KeywordExperienceRetriever:
    """确定性关键词召回：按 ticker > sector > tag 命中度排序。

    零新依赖、可离线单测。命中分相同则「更近期（created_at/date 大）」优先。
    """

    TICKER_WEIGHT = 3.0
    SECTOR_WEIGHT = 2.0
    TAG_WEIGHT = 1.0

    def __init__(self, store: ExperienceStore):
        self._store = store

    def _score(
        self,
        exp: Experience,
        ticker: str,
        sector: Optional[str],
        tagset: set,
    ) -> float:
        score = 0.0
        if ticker and exp.ticker == ticker:
            score += self.TICKER_WEIGHT
        if sector and exp.sector and exp.sector == sector:
            score += self.SECTOR_WEIGHT
        if tagset and exp.tags:
            score += self.TAG_WEIGHT * len(tagset & set(exp.tags))
        return score

    def retrieve(
        self,
        *,
        ticker: str,
        sector: Optional[str] = None,
        tags: Optional[List[str]] = None,
        k: int = 3,
    ) -> List[Experience]:
        try:
            tkr = str(ticker).strip().upper()
            sec = str(sector).strip().upper() if sector else None
            tagset = {str(t).strip().lower() for t in (tags or []) if str(t).strip()}
            scored = []
            for exp in self._store.load():
                s = self._score(exp, tkr, sec, tagset)
                if s > 0:
                    scored.append((s, exp.created_at or exp.date or "", exp))
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return [exp for _, _, exp in scored[: max(0, int(k))]]
        except Exception:  # noqa: BLE001 - 检索失败一律降级为空，不崩主链路
            return []


class StaticExperienceRetriever:
    """测试/注入用：返回构造时给定的经验列表（按 k 截断）。"""

    def __init__(self, items: List[Experience]):
        self._items = list(items)

    def retrieve(self, *, ticker: str = "", sector: Optional[str] = None,
                 tags: Optional[List[str]] = None, k: int = 3) -> List[Experience]:
        return self._items[: max(0, int(k))]


# ---------------------------------------------------------------------------
# V10.29: 失败根因检索（从 trace 中提取失败经验）
# ---------------------------------------------------------------------------
@dataclass
class FailureTrace:
    """从 trace 中提取的失败记录（可检索）。"""

    task_id: str
    ticker: str
    timestamp: str
    phase: str
    failure_root_cause: str
    failure_detail: str
    score: float = 0.0

    def to_experience(self) -> Experience:
        """转换为 Experience 对象（用于注入 Hypothesis 生成）。"""
        return Experience(
            ticker=self.ticker,
            date=self.timestamp[:10] if self.timestamp else "",
            stances={},
            alpha=-1.0,  # 失败经验，alpha 为负
            realized_base=0.0,
            verdict=VERDICT_REFUTED,
            lesson=f"[{self.failure_root_cause}] {self.failure_detail}",
            tags=[f"failure:{self.failure_root_cause}"],
        )


class FailureRootCauseRetriever:
    """从 trace 文件中检索失败根因（V10.29 失败资产化）。

    用法：
        retriever = FailureRootCauseRetriever()
        failures = retriever.retrieve(ticker="AAPL", failure_root_cause="missing_data")
    """

    def __init__(self, trace_dir: Optional[str] = None):
        try:
            from .trace_recorder import default_trace_dir
        except ImportError:
            from trace_recorder import default_trace_dir
        self.trace_dir = trace_dir or default_trace_dir()

    def _load_traces(self) -> List[Dict]:
        """加载所有 trace 文件。"""
        import os
        traces = []
        if not os.path.isdir(self.trace_dir):
            return traces
        for filename in os.listdir(self.trace_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.trace_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    traces.extend(data)
            except (json.JSONDecodeError, OSError):
                continue
        return traces

    def retrieve(
        self,
        *,
        ticker: str = "",
        failure_root_cause: str = "",
        k: int = 3,
    ) -> List[FailureTrace]:
        """检索失败 trace。

        Args:
            ticker: 标的代码（可选，空则匹配所有）
            failure_root_cause: 失败根因分类（可选，空则匹配所有失败）
            k: 返回数量

        Returns:
            失败 trace 列表（按时间倒序）
        """
        try:
            traces = self._load_traces()
            tkr = str(ticker).strip().upper()
            frc = str(failure_root_cause).strip().lower()

            matched = []
            for t in traces:
                # 过滤：必须有 failure_root_cause 且不是 "none"
                root_cause = str(t.get("failure_root_cause", "")).strip().lower()
                if not root_cause or root_cause == "none":
                    continue
                # 过滤：ticker 匹配
                if tkr and str(t.get("ticker", "")).strip().upper() != tkr:
                    continue
                # 过滤：failure_root_cause 匹配
                if frc and root_cause != frc:
                    continue
                matched.append(FailureTrace(
                    task_id=str(t.get("task_id", "")),
                    ticker=str(t.get("ticker", "")),
                    timestamp=str(t.get("timestamp", "")),
                    phase=str(t.get("phase", "")),
                    failure_root_cause=root_cause,
                    failure_detail=str(t.get("failure_detail", "")),
                    score=float(t.get("score", 0.0)),
                ))

            # 按时间倒序
            matched.sort(key=lambda x: x.timestamp, reverse=True)
            return matched[: max(0, int(k))]
        except Exception:  # noqa: BLE001 - 检索失败一律降级为空，不崩主链路
            return []

    def retrieve_as_experiences(
        self,
        *,
        ticker: str = "",
        failure_root_cause: str = "",
        k: int = 3,
    ) -> List[Experience]:
        """检索失败 trace 并转换为 Experience 对象。"""
        return [ft.to_experience() for ft in self.retrieve(
            ticker=ticker,
            failure_root_cause=failure_root_cause,
            k=k,
        )]
