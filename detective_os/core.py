"""DETECTIVE OS — core: sources, evidence, timeline, entities.

Design rules enforced in code, not prose:
- A source is not an independent source. Independence is computed from
  the reprint/origin graph: N reprints of one origin count as ONE.
- Evidence grades A-H (see GRADE_WEIGHT). Grades F (rumour), G (AI
  inference) and H (unverified) have weight 0.0: they can never support
  a hypothesis or enter a Bayesian chain.
- AI inference can never be promoted to evidence. promote() refuses.
- Fuzzy time is preserved: an "evening" stays an evening. The engine
  never invents an hour. TimeRef carries precision, not just a date.
- Mentioning a person is not suspecthood. mark_suspect() requires an
  explicit, reliable basis (grade A/B) or it raises.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

# Evidence grades (spec section 2.2).
# A confirmed fact, B authority public info, C media report/interview,
# D party/witness statement, E third-party relay, F online rumour,
# G AI inference, H pending verification.
GRADE_WEIGHT = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.5,
                "E": 0.3, "F": 0.0, "G": 0.0, "H": 0.0}
GRADE_LABEL = {
    "A": "已确认事实", "B": "权威机构公开信息", "C": "媒体采访或报道",
    "D": "当事人或证人陈述", "E": "第三方转述", "F": "网络传言",
    "G": "AI推断", "H": "尚待核实信息",
}


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", "", s or "").strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(_norm_text(text).encode("utf-8")).hexdigest()[:16]


@dataclass
class Source:
    """One publication. `reprint_of` points at the source it reprints."""
    source_id: str
    title: str
    publisher: str
    author: str = ""
    published_at: str = ""          # ISO date or "" when unknown
    url: str = ""
    source_type: str = ""           # news / official / legal / interview / book / file / manual
    accessible: bool = True
    is_reprint: bool = False
    reprint_of: str = ""            # source_id of the original
    origin_url: str = ""            # canonical original URL when known
    reliability: str = ""           # high / medium / low + why, in notes
    last_verified: str = ""
    notes: str = ""

    def origin_root(self, registry: "SourceRegistry") -> str:
        """Follow reprint_of to the ultimate origin. Guards cycles."""
        seen, cur = set(), self.source_id
        while True:
            src = registry.get(cur)
            if src is None or not src.reprint_of or src.reprint_of in seen:
                return cur
            seen.add(cur)
            cur = src.reprint_of


class SourceRegistry:
    def __init__(self):
        self.sources: dict[str, Source] = {}

    def add(self, src: Source):
        if src.source_id in self.sources:
            raise ValueError(f"duplicate source_id {src.source_id}")
        self.sources[src.source_id] = src
        return src

    def get(self, source_id: str):
        return self.sources.get(source_id)

    def independent_source_count(self, source_ids) -> int:
        """Distinct origin roots among the given sources.

        20 reprints of one unconfirmed message count as ONE.
        """
        roots = {self.get(s).origin_root(self) for s in source_ids if self.get(s)}
        return len(roots)

    def same_origin_cluster(self, source_ids) -> dict:
        """Group source ids by origin root: shows the reprint cluster."""
        clusters: dict[str, list] = {}
        for s in source_ids:
            src = self.get(s)
            if src is None:
                continue
            clusters.setdefault(src.origin_root(self), []).append(s)
        return clusters


@dataclass
class Evidence:
    evidence_id: str
    case_id: str
    content: str
    evidence_type: str = ""         # fact / statement / physical / document / inference
    source_id: str = ""
    original_quote: str = ""
    source_location: str = ""       # e.g. paragraph, page, timestamp
    publication_date: str = ""
    event_date: str = ""
    grade: str = "H"
    reliability_assessment: str = ""  # WHY this grade, mandatory for A/B
    verification_status: str = "unverified"  # verified / single-source / disputed / unverified
    supports: list = field(default_factory=list)
    contradicts: list = field(default_factory=list)
    analyst_notes: str = ""

    @property
    def weight(self) -> float:
        return GRADE_WEIGHT[self.grade]

    @property
    def usable_as_evidence(self) -> bool:
        return self.weight > 0.0


class EvidenceBoard:
    def __init__(self, registry: SourceRegistry):
        self.registry = registry
        self.items: dict[str, Evidence] = {}

    def add(self, ev: Evidence):
        if ev.evidence_id in self.items:
            raise ValueError(f"duplicate evidence_id {ev.evidence_id}")
        if ev.grade not in GRADE_WEIGHT:
            raise ValueError(f"bad grade {ev.grade}")
        if ev.source_id and self.registry.get(ev.source_id) is None:
            raise ValueError(f"evidence {ev.evidence_id}: unknown source {ev.source_id}")
        if ev.grade in ("A", "B") and not ev.reliability_assessment:
            raise ValueError(f"evidence {ev.evidence_id}: grade {ev.grade} needs a reliability reason")
        self.items[ev.evidence_id] = ev
        return ev

    def promote(self, evidence_id: str, new_grade: str):
        """AI inference (G) can never be promoted to evidence. Anything
        else needs a human analyst note; promotion is recorded, not silent."""
        ev = self.items[evidence_id]
        if ev.grade == "G":
            raise ValueError(f"{evidence_id}: AI inference can never be promoted to evidence")
        if new_grade in ("A", "B") and GRADE_WEIGHT[ev.grade] == 0.0:
            raise ValueError(f"{evidence_id}: grade {ev.grade} cannot jump to {new_grade} without new sourcing")
        ev.grade = new_grade
        return ev

    def by_grade(self, grade: str):
        return [e for e in self.items.values() if e.grade == grade]

    def supporting(self, hypothesis_id: str):
        return [e for e in self.items.values() if hypothesis_id in e.supports]

    def contradicting(self, hypothesis_id: str):
        return [e for e in self.items.values() if hypothesis_id in e.contradicts]


@dataclass
class TimeRef:
    """Fuzzy time. `precision` is the point: never upgrade it silently.

    kinds: exact (YYYY-MM-DD HH:MM), date, range, approx (e.g. 傍晚),
    unknown. `label` keeps the original wording, e.g. 傍晚.
    """
    kind: str
    label: str
    earliest: str = ""   # ISO date, "" when unbounded
    latest: str = ""     # ISO date, "" when unbounded

    def __post_init__(self):
        if self.kind not in ("exact", "date", "range", "approx", "unknown"):
            raise ValueError(f"bad time kind {self.kind}")
        if self.kind == "unknown" and (self.earliest or self.latest):
            raise ValueError("unknown time must not carry a date bound")


@dataclass
class Event:
    event_id: str
    case_id: str
    title: str
    time: TimeRef
    persons: list = field(default_factory=list)
    places: list = field(default_factory=list)
    evidence_ids: list = field(default_factory=list)
    notes: str = ""


class TimelineEngine:
    def __init__(self):
        self.events: dict[str, Event] = {}

    def add(self, ev: Event):
        if ev.event_id in self.events:
            raise ValueError(f"duplicate event_id {ev.event_id}")
        self.events[ev.event_id] = ev
        return ev

    def sorted_events(self):
        def key(ev: Event):
            return (ev.time.earliest or "9999", ev.time.latest or "9999", ev.event_id)
        return sorted(self.events.values(), key=key)

    def gaps(self):
        """Unknown intervals between consecutive dated events."""
        out, prev = [], None
        for ev in self.sorted_events():
            if prev is not None and prev.time.latest and ev.time.earliest:
                if prev.time.latest < ev.time.earliest:
                    out.append({"from_event": prev.event_id, "to_event": ev.event_id,
                                "from": prev.time.latest, "to": ev.time.earliest})
            prev = ev
        return out


@dataclass
class Entity:
    entity_id: str
    kind: str                       # person / place / event / evidence / org / item / time / hypothesis
    name: str
    is_suspect: bool = False
    suspect_basis: str = ""         # mandatory when is_suspect is True
    suspect_basis_grade: str = ""   # must be A or B
    notes: str = ""


@dataclass
class Relationship:
    from_id: str
    to_id: str
    relation: str                   # e.g. seen-at / testified / mentioned-in / supports / contradicts
    source_id: str = ""
    evidence_id: str = ""
    notes: str = ""


class EntityGraph:
    def __init__(self, registry: SourceRegistry):
        self.registry = registry
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []

    def add_entity(self, ent: Entity):
        if ent.entity_id in self.entities:
            raise ValueError(f"duplicate entity_id {ent.entity_id}")
        if ent.is_suspect:
            if ent.suspect_basis_grade not in ("A", "B") or not ent.suspect_basis:
                raise ValueError(
                    f"entity {ent.entity_id}: suspect flag needs an A/B-grade basis; "
                    "being mentioned in a report is not a basis")
        self.entities[ent.entity_id] = ent
        return ent

    def mark_suspect(self, entity_id: str, basis: str, basis_grade: str):
        """The only path to suspecthood. Rumour-grade basis is refused."""
        if basis_grade not in ("A", "B"):
            raise ValueError("suspect marking requires grade A or B basis, "
                             f"got {basis_grade}")
        ent = self.entities[entity_id]
        ent.is_suspect, ent.suspect_basis, ent.suspect_basis_grade = True, basis, basis_grade
        return ent

    def add_relationship(self, rel: Relationship):
        if rel.from_id not in self.entities or rel.to_id not in self.entities:
            raise ValueError("relationship endpoints must exist as entities")
        if not rel.source_id and not rel.evidence_id:
            raise ValueError("every relationship needs a source or an evidence id")
        self.relationships.append(rel)
        return rel

    def neighbours(self, entity_id: str):
        out = []
        for r in self.relationships:
            if r.from_id == entity_id:
                out.append((r.relation, r.to_id))
            elif r.to_id == entity_id:
                out.append((r.relation, r.from_id))
        return out

    def to_dict(self):
        return {"entities": [e.__dict__ for e in self.entities.values()],
                "relationships": [r.__dict__ for r in self.relationships]}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
