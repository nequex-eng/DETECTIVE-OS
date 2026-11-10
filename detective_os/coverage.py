"""DETECTIVE OS — source-coverage checklist (module 9).

Added 2026-11-10 on the user's order ("coverage module first, then pick
the case"). Purpose: make "how complete is this case's material?" a
measured number instead of a feeling, and make the collection paths
explicit instead of "whoever searched the web".

Rules enforced in code, not prose:
- Coverage counts only usable evidence (grade weight > 0, i.e. A-E).
  F (rumour), G (AI inference) and H (unverified) never count, even
  when linked to an item: the item stays "missing" and is flagged
  `only_unusable` so a lead is never dressed up as coverage.
- Independence is computed from the reprint/origin graph, the same
  rule as the rest of the engine: 20 reprints of one origin count as
  ONE. An item is "covered" only with >= 2 independent origins.
- A missing item is a fact, not a failure. The checklist exists to
  list gaps honestly; a case with 40% coverage and a complete gap list
  is better than a case that claims 100% on reprints.
- Public sources can never reach full coverage of a criminal file:
  undisclosed police evidence is structurally out of reach. The
  coverage report says so, and the score is always "of the defined
  checklist", never "of the truth".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Collection paths. `community_lead` is leads only: it can point at a
# trail, it can never itself count as evidence (F-grade by construction).
COLLECTION_PATHS = {
    "web_search": "网上搜索（搜索引擎与新闻档案）",
    "direct_source": "直接读源头（通讯社/法院/警方/报纸站内）",
    "news_db": "新闻数据库（GDELT等）",
    "web_archive": "网页档案（Common Crawl、时光机）",
    "court_db": "法院/判例数据库（CourtListener、BAILII等）",
    "local_language": "本地语言搜索（案件发生地语言）",
    "books_media": "书/纪录片/播客文字稿",
    "user_supplied": "用户供料（PDF、剪报、文档）",
    "community_lead": "线索类社区（只当线索，不当证据）",
    "foia": "信息公开申请（FOIA/FOI）",
}
PATH_STATUSES = ("tried", "found", "nothing", "not_applicable")

# Generic cold-case template: 10 categories, 22 items. A case pack
# starts from this template and may add case-specific items; it may
# not silently drop template items (a dropped item must stay in the
# file marked not_applicable with a reason).
CHECKLIST_TEMPLATE = [
    ("失踪/案发", "C01", "被害人身份", "被害人是谁：姓名、年龄、职业或学校、籍贯？"),
    ("失踪/案发", "C02", "最后行踪", "最后一次被可靠记录的时间、地点、最后接触者？"),
    ("失踪/案发", "C03", "案发时间窗口", "遇害或案发的时间范围能否确定？"),
    ("失踪/案发", "C04", "案发地点/第一现场", "第一现场在哪里？有无原始记录？"),
    ("发现", "C05", "发现时间地点与发现者", "何时、何地、何人发现？"),
    ("发现", "C06", "现场状况", "发现时遗体或现场的状况如何描述？"),
    ("身份确认", "C07", "身份确认过程与时间", "如何确认死者身份？何时确认？"),
    ("身份确认", "C08", "认尸/协查原始材料", "认尸启示、协查通报的原始版面是否收入？"),
    ("法医/物证", "C09", "法医结论", "死因、死亡时间的法医结论是什么？"),
    ("法医/物证", "C10", "物证清单与保存现状", "物证有哪些？是否保存、可否复检？"),
    ("法医/物证", "C11", "DNA/指纹比对现状", "DNA、指纹比对做过没有？结果如何？"),
    ("侦查过程", "C12", "排查规模与范围", "排查了多少人、多大范围？有无原始说明？"),
    ("侦查过程", "C13", "侦查节点", "专案组、重启、悬赏等关键节点的时间线？"),
    ("侦查过程", "C14", "嫌疑人画像/排查方向", "公开的画像或排查方向是什么？（方向不等于指认）"),
    ("作案手法", "C15", "作案手法特征", "手法特征的可靠描述有哪些？"),
    ("作案手法", "C16", "抛尸/藏匿方式与路线", "抛尸或藏匿的方式、顺序、路线？"),
    ("动机", "C17", "动机指向", "有无经核实的动机指向？无指向本身也要记录。"),
    ("法律程序", "C18", "诉讼/审判进展", "诉讼、审判、执行进展如何？"),
    ("法律程序", "C19", "追诉时效/立案状态", "立案状态与追诉时效的官方说法？"),
    ("家属与当事人", "C20", "家属说法与诉求", "家属的说法、诉求与时间线？"),
    ("官方回应", "C21", "警方/官方公开回应", "警方与官方的公开回应及时间？"),
    ("官方回应", "C22", "同期原始报道", "案发同期的原始报道是否系统收入？"),
]

TEMPLATE_VERSION = "1"


def template_items():
    """The template as a list of dicts (stable order)."""
    return [{"item_id": iid, "category": cat, "title": title, "question": q}
            for cat, iid, title, q in CHECKLIST_TEMPLATE]


@dataclass
class CoverageItem:
    item_id: str
    category: str
    title: str
    question: str
    evidence_ids: list = field(default_factory=list)
    paths_tried: list = field(default_factory=list)  # [{path, status, note}]
    analyst_note: str = ""
    # computed fields (filled by compute(), not stored in the pack)
    status: str = "missing"          # covered / single / missing
    origins: int = 0                 # independent origins among countable evidence
    only_unusable: bool = False      # linked evidence exists but none counts
    not_applicable: bool = False     # template item explicitly N/A for this case

    def to_dict(self):
        return {"item_id": self.item_id, "category": self.category,
                "title": self.title, "question": self.question,
                "evidence_ids": list(self.evidence_ids),
                "paths_tried": [dict(p) for p in self.paths_tried],
                "analyst_note": self.analyst_note,
                "not_applicable": self.not_applicable}


class CoverageChecklist:
    """A case's coverage checklist: template items + case-specific extras."""

    def __init__(self, case_id: str, items):
        self.case_id = case_id
        self.items = list(items)

    @classmethod
    def from_dict(cls, data: dict):
        items = []
        for d in data.get("items", []):
            items.append(CoverageItem(
                item_id=d["item_id"], category=d["category"],
                title=d["title"], question=d["question"],
                evidence_ids=list(d.get("evidence_ids", [])),
                paths_tried=[dict(p) for p in d.get("paths_tried", [])],
                analyst_note=d.get("analyst_note", ""),
                not_applicable=bool(d.get("not_applicable", False))))
        return cls(data["case_id"], items)

    @classmethod
    def from_template(cls, case_id: str):
        return cls(case_id, [CoverageItem(**d) for d in template_items()])

    @classmethod
    def load(cls, case_dir):
        """Load coverage.json from a case pack; None when the pack has none."""
        p = Path(case_dir) / "coverage.json"
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self):
        return {"case_id": self.case_id, "template_version": TEMPLATE_VERSION,
                "items": [it.to_dict() for it in self.items]}

    def save(self, case_dir):
        p = Path(case_dir) / "coverage.json"
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return p

    def validate(self, board) -> list:
        """Structural problems. Returns a list of strings (empty = clean).

        A linked-but-unusable evidence id is NOT an error: it is a
        lead, and compute() flags it. Unknown evidence ids and unknown
        collection paths are errors.
        """
        problems = []
        seen = set()
        for it in self.items:
            if it.item_id in seen:
                problems.append(f"{it.item_id}: duplicate item id")
            seen.add(it.item_id)
            for eid in it.evidence_ids:
                if eid not in board.items:
                    problems.append(f"{it.item_id}: unknown evidence {eid}")
            for p in it.paths_tried:
                if p.get("path") not in COLLECTION_PATHS:
                    problems.append(f"{it.item_id}: unknown collection path {p.get('path')}")
                if p.get("status") not in PATH_STATUSES:
                    problems.append(f"{it.item_id}: bad path status {p.get('status')}")
        return problems

    def compute(self, board, registry) -> dict:
        """Score every item against the evidence board.

        Countable = linked evidence with weight > 0 (grades A-E).
        Origins = distinct origin roots among the countable evidence's
        sources. covered >= 2 origins, single == 1, missing == 0.
        """
        for it in self.items:
            if it.not_applicable:
                it.status, it.origins, it.only_unusable = "missing", 0, False
                continue
            linked = [board.items[e] for e in it.evidence_ids if e in board.items]
            countable = [e for e in linked if e.usable_as_evidence]
            it.only_unusable = bool(linked) and not countable
            it.origins = registry.independent_source_count(
                [e.source_id for e in countable if e.source_id])
            it.status = ("covered" if it.origins >= 2 else
                         "single" if it.origins == 1 else "missing")
        applicable = [it for it in self.items if not it.not_applicable]
        covered = [it for it in applicable if it.status == "covered"]
        single = [it for it in applicable if it.status == "single"]
        missing = [it for it in applicable if it.status == "missing"]
        total = len(applicable)
        score = (len(covered) + 0.5 * len(single)) / total if total else 0.0
        by_category = {}
        for it in applicable:
            by_category.setdefault(it.category, {"total": 0, "covered": 0,
                                                 "single": 0, "missing": 0})
            by_category[it.category]["total"] += 1
            by_category[it.category][it.status] += 1
        return {"case_id": self.case_id, "template_version": TEMPLATE_VERSION,
                "total": total, "covered": len(covered), "single": len(single),
                "missing": len(missing),
                "only_unusable": sum(1 for it in applicable if it.only_unusable),
                "score": round(score, 4),
                "by_category": by_category,
                "missing_ids": [it.item_id for it in missing],
                "single_ids": [it.item_id for it in single],
                "items": [{"item_id": it.item_id, "category": it.category,
                           "title": it.title, "status": it.status,
                           "origins": it.origins,
                           "only_unusable": it.only_unusable,
                           "evidence_ids": list(it.evidence_ids)}
                          for it in self.items]}

    def markdown_section(self, summary: dict) -> list:
        """Report section lines for the coverage summary."""
        L = ["## 资料覆盖", ""]
        L.append(f"覆盖率：{summary['score'] * 100:.1f}%（{summary['covered']}项已覆盖/"
                 f"{summary['single']}项单来源/{summary['missing']}项缺失，"
                 f"共{summary['total']}项）。覆盖指≥2个独立来源，单来源指只有1个"
                 f"独立来源，传言与待核实不计入覆盖。公开资料永远无法覆盖警方"
                 f"未公开的证据，本数只针对已定义的清单。")
        L.append("")
        for cat, c in summary["by_category"].items():
            L.append(f"- {cat}：{c['covered']}/{c['total']}已覆盖，"
                     f"{c['single']}单来源，{c['missing']}缺失")
        L.append("")
        if summary["missing_ids"]:
            L.append("缺失项：" + "、".join(summary["missing_ids"]) + "。")
            L.append("")
        if summary["single_ids"]:
            L.append("单来源项（只有1个独立来源，需补强）："
                     + "、".join(summary["single_ids"]) + "。")
            L.append("")
        if summary["only_unusable"]:
            L.append(f"另有{summary['only_unusable']}项只有传言或待核实材料，"
                     "不计入覆盖。")
            L.append("")
        return L
