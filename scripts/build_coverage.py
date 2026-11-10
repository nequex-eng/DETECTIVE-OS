#!/usr/bin/env python3
"""Build cases/*/coverage.json from the template + an explicit mapping.

The mapping is the analyst's judgment, written out in the open: every
item links the evidence ids it relies on (or none), and the module
computes the status from those links. Nothing here invents coverage:
an item with no countable evidence scores missing, and a rumour-only
link scores missing with only_unusable=True.

Re-run after editing the mapping: python3 scripts/build_coverage.py
Verify: python -m detective_os.cli coverage cases/case-cn-1996-001
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.coverage import (  # noqa: E402
    CoverageChecklist, CoverageItem, template_items)

FOUND = [{"path": "web_search", "status": "found", "note": "证据来源见evidence_ids"},
         {"path": "direct_source", "status": "found", "note": "来源原文已实读核验"}]
TRIED = [{"path": "web_search", "status": "tried", "note": "公开搜索未见可靠来源"},
         {"path": "direct_source", "status": "tried", "note": "指定来源原文中未见"}]

# item_id -> (evidence_ids, paths, analyst_note, not_applicable)
NANDA = {
    "C01": (["F01"], FOUND, "身份信息来自澎湃家属采访；年龄19岁与年方20岁冲突见CT01。", False),
    "C02": (["F02", "F26"], FOUND, "最后行踪有A级事实；F26证明无公开目击者陈述。", False),
    "C03": ([], TRIED, "缺口G1：遇害时间窗口全未知。", False),
    "C04": (["F11"], FOUND, "只有“未找到第一现场”的B级事实，现场本身未知；缺口G2。", False),
    "C05": (["F03"], FOUND, "发现过程只有新华一家来源。", False),
    "C06": (["F04", "F05"], FOUND, "现场状况两家独立来源。", False),
    "C07": (["F06", "F07"], FOUND, "身份确认过程两家独立来源。", False),
    "C08": (["F14"], FOUND, "认尸启示原文只见于澎湃2016年的引述；原始版面未收入，缺口G7。", False),
    "C09": (["F04", "F07"], FOUND, "法医结论两家独立来源；1996年技术条件有限。", False),
    "C10": ([], TRIED, "缺口G5：物证保存与DNA比对现状未知。", False),
    "C11": ([], TRIED, "缺口G5：DNA/指纹比对现状未知。", False),
    "C12": (["F11", "F17"], FOUND, "排查规模两家独立来源。", False),
    "C13": (["F08", "F10", "F09"], FOUND, "侦查节点三家独立来源（2016公安部、2016家属问询、2022警方回应）。", False),
    "C14": (["F13", "F27"], FOUND, "排查方向两家独立来源；方向不等于指认。", False),
    "C15": (["F04", "F05"], FOUND, "手法特征两家独立来源。", False),
    "C16": (["F05"], FOUND, "抛尸分布只有一家来源；网传骑自行车抛尸（F21）为传言不计入。", False),
    "C17": (["F28"], FOUND, "只有“未见动机证据”的B级事实；缺口G6。", False),
    "C18": (["F15"], FOUND, "2021年诉讼只有中新网一家来源。", False),
    "C19": (["F08", "F18"], FOUND, "追诉时效两条证据同属新华S01一个来源，计1个独立来源。", False),
    "C20": (["F12", "F15", "F16"], FOUND, "家属说法两家独立来源。", False),
    "C21": (["F08", "F09", "F10"], FOUND, "官方回应三家独立来源。", False),
    "C22": (["F14"], FOUND, "同期原始报道只有认尸启示的引述；1996年2月至4月排查同期报道未系统收入，缺口G8。", False),
}

BAIYIN = {
    "C01": (["F01"], FOUND, "被害人只见集体描述，无个人身份档案。", False),
    "C02": (["F03"], FOUND, "最后行踪只有央视一家来源。", False),
    "C03": (["F01"], FOUND, "只有1988–2002总跨度，各案具体时间未公开；缺口G5。", False),
    "C04": (["F03"], FOUND, "只有“进入住所”的描述，第一现场细节未公开；缺口G5。", False),
    "C05": ([], TRIED, "缺口G5：发现时间地点与发现者未见系统公开。", False),
    "C06": (["F03", "F10"], FOUND, "现场状况两家独立来源。", False),
    "C07": ([], TRIED, "截止2016-08-25，被害人身份确认过程未见公开说明。", False),
    "C08": (["F04"], FOUND, "2004宣传提纲只有转述与摘要，原文未收入（F09为H级）。", False),
    "C09": (["F02", "F10"], FOUND, "法医与物证结论两家独立来源。", False),
    "C10": (["F02"], FOUND, "物证清单只有一家来源；比对过程未公开，缺口G4。", False),
    "C11": (["F02", "F05"], FOUND, "DNA/指纹比对两家独立来源。", False),
    "C12": (["F05"], FOUND, "排查规模只有一家来源。", False),
    "C13": (["F01", "F07"], FOUND, "侦查节点两家独立来源。", False),
    "C14": (["F02", "F08"], FOUND, "画像方向两家独立来源；方向不等于指认。", False),
    "C15": (["F03", "F10"], FOUND, "手法特征两家独立来源。", False),
    "C16": ([], [], "被害人均在家中遇害，无抛尸情节，该项不适用。", True),
    "C17": ([], TRIED, "截止2016-08-25，动机指向未见公开说明；缺口G2只涉停手原因。落网后的罪名不在推理范围内。", False),
    "C18": ([], TRIED, "截止2016-08-25未进入诉讼程序（嫌疑人尚未落网）。", False),
    "C19": (["F01"], FOUND, "立案与部督状态只有一家来源。", False),
    "C20": ([], TRIED, "截止2016-08-25，家属说法未见公开报道。", False),
    "C21": (["F01", "F04", "F07"], FOUND, "官方回应三家独立来源。", False),
    "C22": (["F09"], FOUND, "只有H级待核实材料（提纲原文未收入），不计入覆盖。", False),
}

CASES = {
    "CASE-CN-1996-001": ("cases/case-cn-1996-001", NANDA),
    "CASE-CN-1988-001": ("cases/case-cn-1988-001", BAIYIN),
}


def build(case_id, case_dir, mapping):
    items = []
    for t in template_items():
        ev, paths, note, na = mapping.get(t["item_id"], ([], TRIED, "", False))
        items.append(CoverageItem(
            item_id=t["item_id"], category=t["category"], title=t["title"],
            question=t["question"], evidence_ids=list(ev),
            paths_tried=[dict(p) for p in paths], analyst_note=note,
            not_applicable=na))
    cl = CoverageChecklist(case_id, items)
    p = cl.save(ROOT / case_dir)
    print(f"wrote {p} ({len(items)} items)")
    return cl


if __name__ == "__main__":
    for cid, (cdir, mapping) in CASES.items():
        build(cid, cdir, mapping)
