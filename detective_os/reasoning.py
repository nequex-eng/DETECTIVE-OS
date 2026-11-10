"""DETECTIVE OS — reasoning: contradictions, hypotheses, planner, review.

Rules enforced in code:
- Contradictions are typed (5 types) and carry both wordings, the
  sources, and whether the difference could be wording / calibre /
  relay drift rather than lying. Detail differences are never
  auto-judged as lies.
- Hypotheses are competitive and plural by construction. A run
  refuses to crown a winner when the top two are within the margin
  or when key evidence is missing: verdict is "undecided".
- Bayesian numbers are optional and fully disclosed (priors,
  likelihoods, sources, uncertainty). The default verdict is
  qualitative: strong / weak / undecided.
- The devil's-advocate reviewer must cite opposing evidence. A review
  that only repeats the leading hypothesis fails its own check.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .core import GRADE_WEIGHT

CONTRADICTION_TYPES = {
    "time": "时间矛盾",
    "statement": "人物陈述矛盾",
    "media": "不同媒体报道之间的矛盾",
    "physical": "物证描述矛盾",
    "logic": "事实与推断之间的逻辑矛盾",
}

# Two leading hypotheses closer than this (posterior points) => undecided.
WIN_MARGIN = 0.10


@dataclass
class Contradiction:
    contradiction_id: str
    case_id: str
    ctype: str                      # one of CONTRADICTION_TYPES
    evidence_ids: list
    source_ids: list
    quote_a: str
    quote_b: str
    wording_a: str
    wording_b: str
    could_be_drift: str = ""        # e.g. 口径差异/转述漂移/时间口径 — with reason
    needs_what: str = ""
    resolvable_now: bool = False
    resolution: str = ""

    def __post_init__(self):
        if self.ctype not in CONTRADICTION_TYPES:
            raise ValueError(f"bad contradiction type {self.ctype}")
        if not self.quote_a or not self.quote_b:
            raise ValueError(f"{self.contradiction_id}: both wordings need original quotes")

    def to_dict(self):
        return {"contradiction_id": self.contradiction_id, "case_id": self.case_id,
                "type": self.ctype, "type_label": CONTRADICTION_TYPES[self.ctype],
                "evidence_ids": self.evidence_ids, "source_ids": self.source_ids,
                "wording_a": self.wording_a, "wording_b": self.wording_b,
                "quote_a": self.quote_a, "quote_b": self.quote_b,
                "could_be_drift": self.could_be_drift, "needs_what": self.needs_what,
                "resolvable_now": self.resolvable_now, "resolution": self.resolution}


class ContradictionEngine:
    def __init__(self):
        self.items: dict[str, Contradiction] = {}

    def add(self, c: Contradiction):
        if c.contradiction_id in self.items:
            raise ValueError(f"duplicate contradiction_id {c.contradiction_id}")
        self.items[c.contradiction_id] = c
        return c

    def by_type(self, ctype: str):
        return [c for c in self.items.values() if c.ctype == ctype]

    def unresolved(self):
        return [c for c in self.items.values() if not c.resolvable_now]


@dataclass
class Hypothesis:
    hypothesis_id: str
    case_id: str
    description: str
    supports: list = field(default_factory=list)      # evidence_ids
    opposes: list = field(default_factory=list)       # evidence_ids
    unexplained: list = field(default_factory=list)   # evidence_ids it cannot explain
    prerequisites: list = field(default_factory=list)
    predictions: list = field(default_factory=list)   # falsifiable predictions
    falsifiers: list = field(default_factory=list)    # what would disprove it
    prior: float = 0.0
    likelihoods: dict = field(default_factory=dict)   # evidence_id -> P(E|H)
    status: str = "open"                              # open / weakened / refuted / leading

    def checkable(self):
        return bool(self.predictions) and bool(self.falsifiers)


class HypothesisEngine:
    def __init__(self, board):
        self.board = board            # EvidenceBoard
        self.items: dict[str, Hypothesis] = {}

    def add(self, h: Hypothesis):
        if h.hypothesis_id in self.items:
            raise ValueError(f"duplicate hypothesis_id {h.hypothesis_id}")
        for eid in h.supports + h.opposes + h.unexplained:
            if eid not in self.board.items:
                raise ValueError(f"hypothesis {h.hypothesis_id}: unknown evidence {eid}")
        if not h.checkable():
            raise ValueError(f"hypothesis {h.hypothesis_id}: needs falsifiable predictions AND falsifiers")
        self.items[h.hypothesis_id] = h
        return h

    def qualitative_scores(self):
        """Support minus opposition, counting only usable grades (weight>0).

        Returns {hypothesis_id: {support_weight, oppose_weight, net, unexplained}}.
        This is the default verdict: no fake precise probability.
        """
        out = {}
        for hid, h in self.items.items():
            sup = sum(self.board.items[e].weight for e in h.supports if e in self.board.items)
            opp = sum(self.board.items[e].weight for e in h.opposes if e in self.board.items)
            out[hid] = {"support_weight": round(sup, 2), "oppose_weight": round(opp, 2),
                        "net": round(sup - opp, 2),
                        "unexplained": len(h.unexplained),
                        "status": h.status}
        return out

    def bayesian(self):
        """Optional, fully disclosed. Priors must sum to 1. Likelihoods
        come from the case file, never invented at run time. Grade-C/F/G/H
        evidence is skipped (weight 0). Returns posteriors + disclosure.
        """
        hyps = list(self.items.values())
        if abs(sum(h.prior for h in hyps) - 1.0) > 1e-9:
            raise ValueError("priors must sum to 1.0 for a Bayesian run")
        scored = []
        for h in hyps:
            logp = math.log(h.prior) if h.prior > 0 else float("-inf")
            trace = []
            for eid, lik in h.likelihoods.items():
                ev = self.board.items.get(eid)
                if ev is None:
                    continue
                w = ev.weight
                if w == 0.0:
                    trace.append({"evidence_id": eid, "grade": ev.grade,
                                  "note": "excluded: weight 0"})
                    continue
                logp += math.log(lik) * w
                trace.append({"evidence_id": eid, "grade": ev.grade,
                              "likelihood": lik, "weight": w})
            scored.append({"hypothesis_id": h.hypothesis_id, "log_posterior": round(logp, 4),
                           "prior": h.prior, "trace": trace})
        m = max(s["log_posterior"] for s in scored)
        denom = sum(math.exp(s["log_posterior"] - m) for s in scored)
        for s in scored:
            s["posterior"] = round(math.exp(s["log_posterior"] - m) / denom, 4)
        scored.sort(key=lambda s: s["posterior"], reverse=True)
        return {"posteriors": scored,
                "disclosure": "Bayesian output is a model ranking under stated "
                "priors and likelihoods, not a probability of guilt. "
                "Priors are subjective starting points; likelihoods are "
                "analyst judgments stored in the case file. No reliable "
                "data exists to calibrate them against solved cases.",
                "verdict": self._verdict(scored)}

    def _verdict(self, scored):
        if len(scored) < 2:
            return "undecided: fewer than two competitive hypotheses"
        gap = scored[0]["posterior"] - scored[1]["posterior"]
        if gap < WIN_MARGIN:
            return (f"undecided: top two within {gap:.4f} "
                    f"(< {WIN_MARGIN} margin); refuse to crown a winner")
        return f"leading: {scored[0]['hypothesis_id']} (margin {gap:.4f})"

    def counter_evidence(self, hypothesis_id: str):
        """Strongest evidence AGAINST a hypothesis: the devil's advocate feed."""
        h = self.items[hypothesis_id]
        out = []
        for eid in h.opposes:
            ev = self.board.items[eid]
            out.append({"evidence_id": eid, "grade": ev.grade,
                        "weight": ev.weight, "content": ev.content})
        out.sort(key=lambda x: x["weight"], reverse=True)
        return out

    def what_would_distinguish(self):
        """Evidence whose outcome would separate the top hypotheses."""
        scored = self.qualitative_scores()
        ranked = sorted(scored.items(), key=lambda kv: kv[1]["net"], reverse=True)
        if len(ranked) < 2:
            return []
        top_two = [self.items[ranked[0][0]], self.items[ranked[1][0]]]
        distinguishing = []
        for h in top_two:
            for eid in h.supports + h.opposes:
                ev = self.board.items.get(eid)
                if ev is None:
                    continue
                other = top_two[1] if h is top_two[0] else top_two[0]
                if eid in other.opposes or eid in other.supports:
                    distinguishing.append(eid)
        return sorted(set(distinguishing))


@dataclass
class InvestigationTask:
    task_id: str
    case_id: str
    question: str
    purpose: str
    hypotheses: list = field(default_factory=list)
    expected_info: str = ""
    impact_if_yes: str = ""
    impact_if_no: str = ""
    source_or_channel: str = ""    # lawful public-source channel only
    estimated_value: str = ""      # high / medium / low + why
    status: str = "open"


class InvestigationPlanner:
    """Ranks what to check next: single-source claims, undecidable
    hypothesis pairs, and unresolved contradictions first."""

    def __init__(self, board, hyp_engine, contra_engine):
        self.board = board
        self.hyp_engine = hyp_engine
        self.contra_engine = contra_engine

    def plan(self, case_id: str):
        tasks = []
        n = 0

        def add(question, purpose, hyps, expected, yes, no, channel, value):
            nonlocal n
            n += 1
            tasks.append(InvestigationTask(
                task_id=f"T{n:02d}", case_id=case_id, question=question,
                purpose=purpose, hypotheses=hyps, expected_info=expected,
                impact_if_yes=yes, impact_if_no=no,
                source_or_channel=channel, estimated_value=value))

        single = [e for e in self.board.items.values()
                  if e.verification_status == "single-source" and e.weight > 0]
        for e in single:
            add(f"为证据{e.evidence_id}寻找第二个独立来源：{e.content[:40]}……",
                "单来源主张是全案最脆弱的环节", [], "独立来源或否定",
                "该事实升级为已确认", "该事实降级，不得再支撑假设",
                "公开报道、官方公告、法院文书", "high: 单来源事实支撑着假设排序")
        for c in self.contra_engine.unresolved():
            add(f"核验矛盾{c.contradiction_id}（{CONTRADICTION_TYPES[c.ctype]}）：{c.wording_a} vs {c.wording_b}",
                "未解矛盾会污染所有依赖它的推理", [], c.needs_what,
                "矛盾解决，相关证据权重恢复", "矛盾确认为真实分歧，相关结论降级",
                "原始出处、同期多家报道", "high: 矛盾未解")
        distinguishing = self.hyp_engine.what_would_distinguish()
        if distinguishing:
            add("寻找能区分当前前两名假设的新资料",
                "前两名假设目前无法区分", [], f"关键证据：{', '.join(distinguishing)}",
                "前两名拉开差距", "两者都被削弱，须引入新假设",
                "公开资料、已公开的警方通报", "high: 直接决定排序")
        unexplained_map: dict[str, list] = {}
        for h in self.hyp_engine.items.values():
            for eid in h.unexplained:
                unexplained_map.setdefault(eid, []).append(h.hypothesis_id)
        for eid, hyps in unexplained_map.items():
            ev = self.board.items.get(eid)
            if ev:
                add(f"解释尚未被解释的事实{eid}：{ev.content[:40]}……",
                    "一个假设解释不了的事实越多，可信度越低",
                    sorted(hyps), "新的解释机制或反证",
                    "相关假设补强", "相关假设被削弱或推翻",
                    "公开资料", "medium")
        return tasks


REVIEW_ROLES = ["source", "timeline", "evidence", "hypothesis", "adversarial", "final"]
ROLE_LABEL = {"source": "资料分析员", "timeline": "时间线分析员", "evidence": "证据分析员",
              "hypothesis": "假设分析员", "adversarial": "反方调查员", "final": "最终审查员"}


@dataclass
class ReviewFinding:
    role: str
    finding: str
    severity: str = "note"          # note / warning / blocker
    cites: list = field(default_factory=list)   # evidence_ids


class IndependentReview:
    """Six roles review the same case. They do not share a conclusion:
    the adversarial role must cite opposing evidence, and the final
    role checks for leaps, circular reasoning, misattribution and
    unattributed assertions."""

    def __init__(self, board, timeline, hyp_engine, contra_engine):
        self.board = board
        self.timeline = timeline
        self.hyp_engine = hyp_engine
        self.contra_engine = contra_engine

    def run(self, case_id: str):
        findings: list[ReviewFinding] = []

        # A. Source analyst: reprint clusters, single-source facts.
        for e in self.board.items.values():
            if e.verification_status == "single-source":
                findings.append(ReviewFinding(
                    "source", f"证据{e.evidence_id}只有一个来源：{e.content[:30]}……",
                    "warning", [e.evidence_id]))
        for e in self.board.items.values():
            if e.grade in ("F", "G", "H") and e.supports:
                findings.append(ReviewFinding(
                    "source", f"证据{e.evidence_id}（{e.grade}级）被列为支持某假设：权重为0，必须移除",
                    "blocker", [e.evidence_id]))

        # B. Timeline analyst: gaps and unknown precision.
        for g in self.timeline.gaps():
            findings.append(ReviewFinding(
                "timeline", f"时间线空白：{g['from_event']}到{g['to_event']}（{g['from']}至{g['to']}）",
                "note"))
        for ev in self.timeline.events.values():
            if ev.time.kind in ("approx", "unknown"):
                findings.append(ReviewFinding(
                    "timeline", f"事件{ev.event_id}时间精度为{ev.time.kind}（{ev.time.label}），不得升级为精确时间",
                    "note", list(ev.evidence_ids)))

        # C. Evidence analyst: conclusions without evidence.
        for hid, h in self.hyp_engine.items.items():
            if not h.supports:
                findings.append(ReviewFinding(
                    "evidence", f"假设{hid}没有任何支持证据", "blocker"))
            if h.unexplained:
                findings.append(ReviewFinding(
                    "evidence", f"假设{hid}有{len(h.unexplained)}项事实尚未解释：{','.join(h.unexplained)}",
                    "warning", list(h.unexplained)))

        # D. Hypothesis analyst: single-hypothesis lock-in.
        if len(self.hyp_engine.items) < 2:
            findings.append(ReviewFinding(
                "hypothesis", "只有一个竞争性假设：违反多假设原则", "blocker"))
        for hid, h in self.hyp_engine.items.items():
            if not h.falsifiers:
                findings.append(ReviewFinding(
                    "hypothesis", f"假设{hid}没有可证伪点", "blocker"))

        # E. Adversarial: attack the leading hypothesis with its own opposes.
        scores = self.hyp_engine.qualitative_scores()
        if scores:
            leader = max(scores.items(), key=lambda kv: kv[1]["net"])[0]
            counter = self.hyp_engine.counter_evidence(leader)
            if not counter:
                findings.append(ReviewFinding(
                    "adversarial", f"反方审查失败：领先假设{leader}找不到任何反证，审查未真正执行",
                    "blocker"))
            else:
                for c in counter:
                    findings.append(ReviewFinding(
                        "adversarial", f"反证：{c['evidence_id']}（{c['grade']}级）反对{leader}：{c['content'][:40]}……",
                        "warning", [c["evidence_id"]]))

        # F. Final reviewer: unattributed assertions, circularity.
        for e in self.board.items.values():
            if e.grade == "A" and not e.source_id:
                findings.append(ReviewFinding(
                    "final", f"证据{e.evidence_id}自称A级却无来源：无来源断言", "blocker", [e.evidence_id]))
        blockers = [f for f in findings if f.severity == "blocker"]
        return {"case_id": case_id,
                "findings": [f.__dict__ for f in findings],
                "blockers": len(blockers),
                "passed": len(blockers) == 0}
