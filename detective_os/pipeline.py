"""DETECTIVE OS — auto-run pipeline (v1, draft only).

Flow: direction -> plan_queries -> (agent collects sources with
browser.search / browser.open) -> extract_candidates (LLM) ->
build_draft_pack -> run_draft (engine + coverage + report).

What this module does NOT do:
- It never searches the web itself. Collection is the runner's job
  (the agent, with real search tools); this module only plans the
  queries and turns collected texts into a draft pack.
- It never assigns grade A or B. LLM-extracted evidence is capped at
  C (media report) or H (unverified). A/B need a human reliability
  reason, which an LLM cannot supply.
- It never computes probabilities. Hypotheses use the standard
  5-archetype template with uniform priors; likelihoods are LLM
  proposals clamped to [0.2, 0.8], disclosed as unreviewed in the
  draft report. The draft verdict is almost always "undecided",
  which is the correct answer for an unreviewed draft.
- It never invents a quote. extract_candidates verifies every quote
  verbatim against the source text (whitespace-normalized) and drops
  anything that does not match.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from detective_os.coverage import template_items

# Standard 5-archetype hypothesis template for a draft pack.
# Uniform priors: a draft has no basis to favour any archetype yet.
# Predictions/falsifiers are generic template defaults (each is a real
# falsifiable statement); the reviewer replaces them with case-specific
# ones. Likelihoods are LLM proposals, clamped in build_draft_pack.
HYPOTHESIS_TEMPLATE = [
    ("H1", "熟人作案，具备专业技能", 0.2,
     ["公开资料中出现被害人与熟人接触的记录"],
     ["公开资料证明被害人与凶手素不相识"]),
    ("H2", "熟人作案，无专业技能", 0.2,
     ["公开资料中出现被害人与熟人接触的记录"],
     ["现场显示高度专业的手法"]),
    ("H3", "陌生人作案，具备专业技能", 0.2,
     ["公开资料中出现陌生人尾随或搭讪的记录"],
     ["公开资料证明被害人与凶手相识"]),
    ("H4", "陌生人作案，无专业技能", 0.2,
     ["公开资料中出现陌生人尾随或搭讪的记录"],
     ["现场显示高度专业的手法"]),
    ("H5", "团伙作案", 0.2,
     ["公开资料中出现多人协同的痕迹"],
     ["全部证据指向单人作案"]),
]

# Checklist categories the extractor may tag a fact with.
CATEGORIES = [i["item_id"] for i in template_items()]

_QUERY_WORDS = {
    "zh": ["失踪", "发现", "警方", "调查", "时间线", "法医", "嫌疑人画像", "审判", "家属"],
    "en": ["disappearance", "discovery", "police", "investigation", "timeline",
           "forensic", "suspect sketch", "trial", "family"],
}


def plan_queries(direction: str, language: str = "zh", region: str = "",
                 investigation_mode: str = "criminal") -> list:
    """Systematic query plan for a direction.

    Base query + one per checklist angle, in the direction language
    and (when it is not English) in English too. The runner executes
    these with real search; this only plans them so collection is
    systematic instead of ad-hoc.
    """
    direction = direction.strip()
    langs = [language] if language == "en" else [language, "en"]
    general_words = {
        "zh": ["官方文件", "公开记录", "研究报告", "统计数据", "历史档案",
               "组织架构", "决策过程", "财务披露", "政策背景"],
        "en": ["official records", "public documents", "research report",
               "statistics", "historical archives", "organization structure",
               "decision process", "financial filings", "policy background"],
    }
    queries = []
    for lang in langs:
        words = (general_words.get(lang, general_words["en"])
                 if investigation_mode == "general"
                 else _QUERY_WORDS.get(lang, _QUERY_WORDS["en"]))
        queries.append(direction + (f" {region}" if region else ""))
        for w in words:
            queries.append(f"{direction} {w}")
    # de-dupe, keep order
    seen, out = set(), []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _norm(s: str) -> str:
    """Normalize for verbatim comparison: drop whitespace and ALL
    punctuation (ASCII + CJK, curly/straight quotes, full/half width).
    What remains is the letter/digit/CJK skeleton, so a quote that
    differs only in punctuation still verifies, while any reworded
    content still fails."""
    import unicodedata
    return "".join(
        ch for ch in (s or "")
        if not ch.isspace() and unicodedata.category(ch)[0] != "P")


def verify_quote(quote: str, source_text: str) -> bool:
    """True only when the quote appears verbatim (whitespace-insensitive)
    in the source text. The anti-fabrication gate for extraction."""
    q, t = _norm(quote), _norm(source_text)
    return bool(q) and len(q) >= 4 and q in t


EXTRACT_SYSTEM = """你是一名刑事案件档案员，只做一件事：从给定的报道原文里抽出事实。
硬规则：
- 只输出JSON数组，每项：{"content": "一句话事实", "quote": "原文中的逐字引用", "source_location": "段落或位置", "evidence_type": "fact或statement或physical或document", "event_date": "YYYY-MM-DD或空", "category": "C01到C22中的一项或空"}。
- quote必须是原文里逐字出现的一段话，不得改写、不得拼接、不得编造。找不到逐字引用就不要输出这一项。
- content只能复述quote里的内容，不得加推断、不得加“说明”“意味着”这类话。
- 不要输出结论、不要输出假设、不要输出嫌疑人指认。
- 最多输出12项。没有可抽的事实就输出[]。"""

GENERAL_EXTRACT_SYSTEM = """你是一名严谨的通用调查资料分析员，不预设这是刑事案件。
从给定原文中抽取与调查主题直接相关、可核验的事实，包括人物、组织、制度、决策、时间、地点、数据、过程、利益关系、公开声明、历史背景等。
硬规则：
- 只输出JSON数组，每项：{"content":"一句话事实","quote":"原文逐字引用","source_location":"段落或位置","evidence_type":"fact或statement或document或data","event_date":"YYYY-MM-DD或空"}。
- 不得假定存在被害人、犯罪、嫌疑人、警方或违法行为；原文没有就不能引入。
- content只复述quote，不添加解释、因果推断或评价。
- quote必须能在原文中逐字核验；不得改写、拼接或编造。
- 最多输出12项；没有可抽取事实则输出[]。"""


def extract_candidates(source_text: str, source_id: str, direction: str,
                       caller=None, investigation_mode: str = "criminal") -> list:
    """Extract candidate facts from one source text via the LLM.

    `caller` defaults to the retrying MiniMax caller; tests pass a stub.
    Every returned item passed verify_quote against the source text.
    """
    from detective_os.llm import call_minimax_retry
    caller = caller or call_minimax_retry
    user = (f"调查方向：{direction}\n来源编号：{source_id}\n"
            f"报道原文：\n{source_text[:12000]}")
    system_prompt = (GENERAL_EXTRACT_SYSTEM if investigation_mode == "general"
                     else EXTRACT_SYSTEM)
    raw = caller([{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user}],
                 max_tokens=8192, temperature=0.2)
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        quote = str(it.get("quote", ""))
        content = str(it.get("content", "")).strip()
        if not content or not verify_quote(quote, source_text):
            continue
        cat = str(it.get("category", ""))
        out.append({
            "content": content,
            "quote": quote,
            "source_location": str(it.get("source_location", "")),
            "evidence_type": str(it.get("evidence_type", "fact")),
            "event_date": str(it.get("event_date", "")),
            "category": cat if investigation_mode == "criminal" and cat in CATEGORIES else "",
            "source_id": source_id,
        })
    return out


LIKELIHOOD_SYSTEM = """你是一名刑事案件分析员，只做一件事：给每条证据在每个假设下打一个似然值。
硬规则：
- 只输出JSON对象，形如 {"H1": {"F01": 0.7}, "H2": {}, ...}，键是假设编号，值是证据编号到数字的映射。
- 似然 = 在该假设为真的前提下，出现这条证据的可能性。0.5表示中性（证据与假设无关），>0.5表示证据在该假设下更可能出现，<0.5表示更不可能出现。
- 数字只在0.2到0.8之间。没有把握就给0.5，不要猜。
- 不要输出解释、不要输出结论、不要输出嫌疑人指认。"""


def generate_investigation_hypotheses(direction: str, evidence: list,
                                       context: str = "", caller=None) -> list:
    """Generate topic-specific, falsifiable hypotheses for non-criminal investigations."""
    from detective_os.llm import call_minimax_retry
    caller = caller or call_minimax_retry
    facts = "\n".join(
        f"{e.get('evidence_id')}: {e.get('content')}" for e in evidence[:60])
    system = """你是跨领域调查研究员。根据调查主题和已核验事实，提出3至5个彼此有区别、可以被证据检验的竞争性解释或调查假设。
绝不默认这是刑事案件；不得擅自引入被害人、嫌疑人、作案方式、犯罪动机、警方等概念。
假设必须紧扣调查对象与问题，可以是不同成因、机制、决策路径、组织角色、数据解释、历史解释或其他与主题相符的可能性。
只输出JSON数组，每项字段：hypothesis_id(H1起)、description(具体假设)、predictions(至少1条可观察预测)、falsifiers(至少2条可证伪条件)。
不得把事实写成假设，不得把未经证实的可能性写成结论。不同假设应尽量互相区分。"""
    user = (f"调查主题：{direction}\n补充调查要求：{context[:5000]}\n"
            f"已核验候选事实（仅作背景，不代表最终确认）：\n{facts or '暂无候选事实'}")
    raw = caller([{"role": "system", "content": system},
                  {"role": "user", "content": user}],
                 max_tokens=5000, temperature=0.2)
    match = re.search(r"\[.*\]", raw, re.S)
    if not match:
        raise ValueError("纯调查模式未能生成结构化假设；已停止，不会套用刑事案件假设模板。")
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("纯调查假设格式无效；已停止，不会套用刑事案件假设模板。") from exc
    valid, seen = [], set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        desc = str(row.get("description", "")).strip()
        preds = [str(x).strip() for x in row.get("predictions", []) if str(x).strip()]
        fals = [str(x).strip() for x in row.get("falsifiers", []) if str(x).strip()]
        if not desc or not preds or len(fals) < 2:
            continue
        if any(term in desc for term in ("熟人作案", "陌生人作案", "团伙作案", "被害人", "凶手", "作案手法")):
            continue
        key = desc.casefold()
        if key in seen:
            continue
        seen.add(key)
        valid.append({
            "hypothesis_id": f"H{len(valid)+1}", "description": desc,
            "supports": [], "opposes": [], "unexplained": [], "prerequisites": [],
            "predictions": preds[:4], "falsifiers": fals[:4],
            "prior": 1.0, "likelihoods": {}, "status": "open",
        })
    if len(valid) < 2:
        raise ValueError("纯调查模式至少需要两个相关且可证伪的假设；已停止，不会套用刑事案件假设模板。")
    for row in valid:
        row["prior"] = 1.0 / len(valid)
    return valid

def propose_likelihoods(evidence: list, caller=None,
                        batch_size: int = 10, hypotheses: list | None = None,
                        investigation_mode: str = "criminal") -> dict:
    """Propose disclosed likelihoods for the supplied hypotheses."""
    from detective_os.llm import call_minimax_retry
    caller = caller or call_minimax_retry
    if not evidence:
        return {}
    if hypotheses:
        hyps = "\n".join(f"{h.get('hypothesis_id')}：{h.get('description')}"
                         for h in hypotheses)
        valid_h = {h.get("hypothesis_id") for h in hypotheses}
    else:
        hyps = "\n".join(f"{h}：{d}" for h, d, *_ in HYPOTHESIS_TEMPLATE)
        valid_h = {h for h, *_ in HYPOTHESIS_TEMPLATE}
    out = {}
    for start in range(0, len(evidence), batch_size):
        chunk = evidence[start:start + batch_size]
        lines = [f"{ev['evidence_id']}：{ev['content']}" for ev in chunk]
        user = (f"调查模式：{'纯调查' if investigation_mode == 'general' else '刑事调查'}\n"
                f"假设：\n{hyps}\n\n证据：\n" + "\n".join(lines))
        system_prompt = ("""你是通用调查分析员。评估每条事实在各竞争性假设成立时出现的相对可能性。
不得预设犯罪、被害人、嫌疑人或作案方式。只输出JSON对象：假设编号 -> 证据编号 -> 0.2至0.8的数值。
0.5代表中性或无法判断；没有依据时使用0.5，不得编造事实或输出结论。""" if investigation_mode == "general"
                         else LIKELIHOOD_SYSTEM)
        try:
            raw = caller([{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user}],
                         max_tokens=8192, temperature=0.2)
        except Exception as exc:  # noqa: BLE001
            print(f"likelihood batch {start}-{start + len(chunk) - 1} failed ({exc}); skipping")
            continue
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            continue
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        for hid, mapping in data.items():
            if hid not in valid_h or not isinstance(mapping, dict):
                continue
            for eid, value in mapping.items():
                try:
                    out[(hid, eid)] = float(value)
                except (TypeError, ValueError):
                    continue
    return out

CATEGORY_MAP_SYSTEM = """你是一名刑事案件档案员，只做一件事：把每条证据对应到资料覆盖清单的条目上。
硬规则：
- 只输出JSON对象，形如 {"F01": ["C13"], "F02": ["C07", "C21"]}，键是证据编号，值是清单条目编号的数组，每条证据最多2个条目。
- 条目编号只能用下面清单里给出的编号，不得自造。
- 只有证据内容确实回答了该条目问的问题，才对应；不确定就不要对应。
- 不要输出解释、不要输出结论。"""


def map_categories(evidence: list, caller=None,
                   batch_size: int = 15) -> dict:
    """Map each evidence item to 0-2 coverage-checklist items.

    The extractor is asked for categories but M3 often returns them
    empty, which silently zeroes coverage. This separate, focused call
    does the mapping with the full checklist in context. Batched at 15
    items per call (a 70-item single call returns empty). Returns
    {evidence_id: [item_id, ...]}; anything invalid is dropped.
    """
    from detective_os.coverage import template_items
    from detective_os.llm import call_minimax_retry
    caller = caller or call_minimax_retry
    if not evidence:
        return {}
    items = template_items()
    checklist = "\n".join(
        f"{i['item_id']}（{i['category']}）：{i['title']}——{i['question']}"
        for i in items)
    valid = {i["item_id"] for i in items}
    out = {}
    for start in range(0, len(evidence), batch_size):
        chunk = evidence[start:start + batch_size]
        evs = "\n".join(f"{e['evidence_id']}：{e['content']}" for e in chunk)
        user = f"资料覆盖清单：\n{checklist}\n\n证据：\n{evs}"
        try:
            raw = caller([{"role": "system", "content": CATEGORY_MAP_SYSTEM},
                          {"role": "user", "content": user}],
                         max_tokens=4096, temperature=0.2)
        except Exception as exc:  # noqa: BLE001 - one flaky batch must
            # not kill the run; its evidence stays unmapped (coverage
            # honestly lower, not fabricated).
            print(f"mapping batch {start}-{start + len(chunk) - 1} "
                  f"failed ({exc}); skipping")
            continue
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            continue
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        ev_ids = {e["evidence_id"] for e in chunk}
        for eid, cats in data.items():
            if eid not in ev_ids or not isinstance(cats, list):
                continue
            keep = [c for c in cats if c in valid][:2]
            if keep:
                out[eid] = keep
    return out


def _normalize_paths(paths_tried):
    """Map free-form collection notes to the coverage checklist's
    canonical {path, status} vocabulary.

    The collector writes free-form notes ("browser.search news
    vertical: ...", "browser.open xinhuanet.com/...") with statuses
    like "ok"/"partial", but CoverageChecklist.validate() only accepts
    the 10 COLLECTION_PATHS names and the 4 PATH_STATUSES. Copying the
    notes verbatim made every draft pack fail validation at the engine
    step (E2E run 8, 2026-11-11). Unknown entries fall back to
    web_search/tried; the raw strings are returned too, so the caller
    can keep them in the analyst note instead of silently dropping
    them. Returns (normalized_list, raw_strings).
    """
    out = []
    raw = []
    for p in paths_tried or []:
        name = str(p.get("path", ""))
        status = str(p.get("status", ""))
        raw.append(f"{name} ({status})" if status else name)
        low = name.lower()
        if "local_language" in low:
            path = "local_language"
        elif "open" in low or "direct_source" in low:
            path = "direct_source"
        elif "archive" in low or "wayback" in low:
            path = "web_archive"
        elif "court" in low:
            path = "court_db"
        elif "news_db" in low or "gdelt" in low:
            path = "news_db"
        elif "book" in low or "podcast" in low or "documentary" in low:
            path = "books_media"
        elif "user_supplied" in low:
            path = "user_supplied"
        elif "community" in low:
            path = "community_lead"
        elif "foia" in low or "公开申请" in name:
            path = "foia"
        else:
            path = "web_search"
        st = {"found": "found", "ok": "found", "tried": "tried",
              "partial": "tried", "nothing": "nothing",
              "not_applicable": "not_applicable"}.get(status, "tried")
        out.append({"path": path, "status": st})
    seen = set()
    deduped = []
    for e in out:
        key = (e["path"], e["status"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped, raw


def build_draft_pack(case_id: str, name: str, direction: str, job_id: str,
                     sources: list, candidates: list, paths_tried: list,
                     likelihoods: dict | None = None,
                     categories: dict | None = None,
                     baseline_hypotheses: list | None = None,
                     investigation_mode: str = "criminal",
                     hypothesis_specs: list | None = None) -> dict:
    """Assemble a draft case pack (dicts, not files) from collected
    sources and verified candidates.

    - sources: [{source_id, title, publisher, published_at, url,
      source_type, is_reprint, reprint_of, notes}]
    - candidates: verified extract_candidates outputs.
    - likelihoods: {(hypothesis_id, evidence_id): float} LLM proposals,
      clamped to [0.2, 0.8]; anything unmapped stays 0.5.
    - categories: {evidence_id: [item_id, ...]} from map_categories;
      falls back to the extractor's single category tag.
    - Newly extracted evidence is grade C, or H when its quote cannot be
      tied to a dated, sourced statement. Explicit archived baseline metadata
      may retain its original A-E grade; new model outputs never upgrade it.
    """
    likelihoods = likelihoods or {}
    categories = categories or {}
    evidence = []
    for i, c in enumerate(candidates, 1):
        eid = f"F{i:02d}"
        cats = categories.get(eid)
        if not cats and c.get("category"):
            cats = [c["category"]]
        evidence.append({
            "evidence_id": eid, "content": c["content"],
            "evidence_type": c.get("evidence_type", "fact"),
            "source_id": c["source_id"], "original_quote": c["quote"],
            "source_location": c.get("source_location", ""),
            "publication_date": "",
            "event_date": c.get("event_date", ""),
            "grade": (str(c.get("baseline_grade", "C")).upper()
                      if str(c.get("baseline_grade", "C")).upper() in ("A", "B", "C", "D", "E")
                      else "C"),
            "reliability_assessment": c.get("baseline_reliability_assessment")
                or "草稿：LLM从报道原文抽取，逐字引用已核验，待人工复核定级。",
            "verification_status": c.get("baseline_verification_status") or "single-source",
            "supports": list(c.get("baseline_supports") or []),
            "contradicts": list(c.get("baseline_contradicts") or []),
            "analyst_notes": c.get("baseline_analyst_notes") or "DRAFT: auto-extracted, unreviewed.",
            "_categories": list(cats or []),
        })
    hypotheses = []
    if baseline_hypotheses:
        for baseline in baseline_hypotheses:
            row = dict(baseline)
            hid = str(row.get("hypothesis_id", ""))
            old_likelihoods = row.get("likelihoods") or {}
            lik = {}
            for ev in evidence:
                value = likelihoods.get(
                    (hid, ev["evidence_id"]),
                    old_likelihoods.get(ev["evidence_id"], 0.5))
                lik[ev["evidence_id"]] = max(0.2, min(0.8, float(value)))
            row["likelihoods"] = lik
            row["supports"] = list(row.get("supports") or [])
            row["opposes"] = list(row.get("opposes") or [])
            row["unexplained"] = list(row.get("unexplained") or [])
            if investigation_mode == "general":
                row["supports"] = sorted(set(row["supports"]) | {
                    eid for eid, value in lik.items() if value >= 0.6})
                row["opposes"] = sorted(set(row["opposes"]) | {
                    eid for eid, value in lik.items() if value <= 0.4})
            hypotheses.append(row)
    elif investigation_mode == "general":
        if not hypothesis_specs or len(hypothesis_specs) < 2:
            raise ValueError("纯调查模式缺少至少两个主题相关假设；拒绝使用刑事模板")
        for spec in hypothesis_specs:
            row = dict(spec)
            hid = str(row.get("hypothesis_id", ""))
            row["likelihoods"] = {
                ev["evidence_id"]: max(0.2, min(0.8, float(
                    likelihoods.get((hid, ev["evidence_id"]), 0.5))))
                for ev in evidence
            }
            row["supports"] = [eid for eid, value in row["likelihoods"].items() if value >= 0.6]
            row["opposes"] = [eid for eid, value in row["likelihoods"].items() if value <= 0.4]
            hypotheses.append(row)
    else:
        for hid, desc, prior, preds, fals in HYPOTHESIS_TEMPLATE:
            lik = {}
            for ev in evidence:
                v = likelihoods.get((hid, ev["evidence_id"]), 0.5)
                lik[ev["evidence_id"]] = max(0.2, min(0.8, float(v)))
            hypotheses.append({
                "hypothesis_id": hid, "description": desc,
                "supports": [], "opposes": [], "unexplained": [],
                "prerequisites": [], "predictions": list(preds),
                "falsifiers": list(fals),
                "prior": prior, "likelihoods": lik, "status": "open",
            })
    case = {
        "case_id": case_id, "name": name, "status": "draft-unreviewed",
        "direction": direction, "job_id": job_id,
        "investigation_mode": investigation_mode,
        "gaps": [{"id": "G0", "gap": "本案包为自动生成的草稿，未经人工复核；"
                  "证据最高C级，假设似然为LLM初拟，结论只作参考。",
                  "needed": "人工复核每条证据的原文与分级，确认假设与似然。"}],
        "limits": (["本报告为未审草稿：证据由LLM从公开来源抽取（逐字引用已核验），"
                   "最高C级；主题假设由模型根据调查问题生成，先验均匀，似然为初拟；须人工复核。"]
                  if investigation_mode == "general" else
                  ["本报告为未审草稿：证据由LLM从公开报道抽取（逐字引用已核验），"
                   "最高C级；假设先验为均匀分布，似然为LLM初拟；不得据此指认任何人。",
                   "公开资料回答不了的问题必须明说，不得假装还原完整刑侦卷宗。"]),
        "hypotheses": hypotheses,
    }
    coverage_items = []
    norm_paths, raw_paths = _normalize_paths(paths_tried)
    for t in (template_items() if investigation_mode == "criminal" else []):
        linked = [e["evidence_id"] for e in evidence
                  if t["item_id"] in e.get("_categories", [])]
        coverage_items.append({
            "item_id": t["item_id"], "category": t["category"],
            "title": t["title"], "question": t["question"],
            "evidence_ids": linked,
            "paths_tried": [dict(p) for p in norm_paths],
            "analyst_note": "DRAFT: auto-linked by category mapping. "
                            "Raw collection notes: " + "; ".join(raw_paths),
            "not_applicable": False,
        })
    for e in evidence:
        e.pop("_categories", None)
    return {
        "case": case, "sources": sources, "evidence": evidence,
        "events": [], "entities": {"entities": [], "relationships": []},
        "contradictions": [],
        "coverage": ({"case_id": case_id, "template_version": "1",
                      "items": coverage_items} if investigation_mode == "criminal" else None),
    }


def write_draft_pack(case_dir: Path, pack: dict) -> Path:
    """Write a draft pack to cases/<dir>/ in the standard layout."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(pack["case"], ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "sources.json").write_text(
        json.dumps(pack["sources"], ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "evidence.json").write_text(
        json.dumps(pack["evidence"], ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "events.json").write_text("[]", encoding="utf-8")
    (case_dir / "entities.json").write_text(
        json.dumps(pack["entities"], ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "contradictions.json").write_text("[]", encoding="utf-8")
    coverage_path = case_dir / "coverage.json"
    if pack.get("coverage") is not None:
        coverage_path.write_text(
            json.dumps(pack["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")
    elif coverage_path.exists():
        coverage_path.unlink()
    return case_dir


DRAFT_BANNER = [
    "# 草稿（未审）— 本报告未经人工复核",
    "",
    "自动流程从公开来源抽取事实，逐字引用已经核验；证据最高C级。"
    "假设由模型初拟，先验与似然均需人工复核。不得将假设或模型排序当作已证实事实。",
    "人工复核每条证据的原文与分级后，方可去掉本横幅。",
    "",
]


def run_draft(case_dir: Path, out_dir: Path):
    """Run the engine + coverage on a draft pack and write the report
    with the DRAFT banner prepended. Returns (report_md_path, summary)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from detective_os.cli import load_case, run_case
    from detective_os.coverage import CoverageChecklist

    case_dir, out_dir = Path(case_dir), Path(out_dir)
    loaded = load_case(case_dir)
    res = run_case(case_dir, out_dir, None)
    cl = CoverageChecklist.load(case_dir)
    summary = cl.compute(loaded["board"], loaded["registry"]) if cl else None
    md_path = out_dir / f"{loaded['case']['case_id']}-report.md"
    md = md_path.read_text(encoding="utf-8")
    md_path.write_text("\n".join(DRAFT_BANNER) + md, encoding="utf-8")
    return md_path, {"bayes": res["bayes"], "coverage": summary,
                     "plan_tasks": res["plan_tasks"],
                     "review": res["review"]}
