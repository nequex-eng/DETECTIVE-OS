"""DETECTIVE OS — auto-run pipeline tests (v1 draft pipeline).

Run: python -m unittest discover -s tests -v
Stdlib only. The LLM is stubbed; the only real text used is the
Baiyin F01 fact already in the case pack.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.pipeline import (  # noqa: E402
    build_draft_pack, extract_candidates, map_categories, plan_queries,
    propose_likelihoods, run_draft, verify_quote, write_draft_pack)

SOURCE_TEXT = ("1988年至2002年，甘肃省白银市发生系列强奸杀人案，作案跨度14年，"
               "多名年轻女性被害；2004年白银市公安局公布详细案情并悬赏20万元征集线索。")

STUB_GOOD = json.dumps([
    {"content": "1988年至2002年白银市发生系列强奸杀人案，跨度14年。",
     "quote": "1988年至2002年，甘肃省白银市发生系列强奸杀人案，作案跨度14年",
     "source_location": "第1段", "evidence_type": "fact",
     "event_date": "", "category": "C13"},
    {"content": "警方悬赏了50万元。",
     "quote": "警方悬赏了50万元征集线索",
     "source_location": "第1段", "evidence_type": "fact",
     "event_date": "", "category": "C13"},
    {"content": "没有引用的事实。",
     "quote": "",
     "source_location": "", "evidence_type": "fact",
     "event_date": "", "category": ""},
], ensure_ascii=False)


def stub_caller(messages, max_tokens=4096, temperature=0.2):
    return STUB_GOOD


class TestPlanQueries(unittest.TestCase):
    def test_zh_direction_gets_zh_and_en_queries(self):
        qs = plan_queries("白银连环杀人案", "zh")
        self.assertEqual(qs[0], "白银连环杀人案")
        self.assertTrue(any("白银连环杀人案 警方" in q for q in qs))
        self.assertTrue(any("白银连环杀人案 police" in q for q in qs))
        self.assertEqual(len(qs), len(set(qs)))


class TestVerifyQuote(unittest.TestCase):
    def test_verbatim_with_whitespace_difference(self):
        self.assertTrue(verify_quote("白银市发生系列\n强奸杀人案", SOURCE_TEXT))

    def test_curly_vs_straight_quotes_still_match(self):
        # Quote wraps the phrase in curly quotes; the source has none.
        self.assertTrue(verify_quote("“白银市发生系列强奸杀人案”", SOURCE_TEXT))

    def test_fullwidth_comma_still_matches(self):
        self.assertTrue(verify_quote("1988年至2002年，甘肃省白银市发生系列强奸杀人案",
                                      SOURCE_TEXT.replace("，", ",")))

    def test_paraphrase_rejected(self):
        self.assertFalse(verify_quote("白银发生了很多命案", SOURCE_TEXT))

    def test_empty_and_short_rejected(self):
        self.assertFalse(verify_quote("", SOURCE_TEXT))
        self.assertFalse(verify_quote("白银", SOURCE_TEXT))


class TestExtract(unittest.TestCase):
    def test_only_verified_quote_survives(self):
        items = extract_candidates(SOURCE_TEXT, "S01", "白银连环杀人案",
                                   caller=stub_caller)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "C13")
        self.assertEqual(items[0]["source_id"], "S01")

    def test_invalid_json_returns_empty(self):
        items = extract_candidates(SOURCE_TEXT, "S01", "白银连环杀人案",
                                   caller=lambda *a, **k: "not json at all")
        self.assertEqual(items, [])


class TestLikelihoods(unittest.TestCase):
    def test_batched_calls(self):
        ev = [{"evidence_id": f"F{i:02d}", "content": f"事实{i}"}
              for i in range(1, 26)]
        calls = []
        def stub(msgs, **k):
            calls.append(msgs[1]["content"])
            return json.dumps({"H1": {"F01": 0.7}})
        out = propose_likelihoods(ev, caller=stub, batch_size=10)
        self.assertEqual(len(calls), 3)  # 25 items -> 3 batches
        self.assertEqual(out[("H1", "F01")], 0.7)

    def test_failed_batch_skipped_not_fatal(self):
        ev = [{"evidence_id": f"F{i:02d}", "content": f"事实{i}"}
              for i in range(1, 26)]
        calls = {"n": 0}
        def stub(msgs, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("minimax returned empty content")
            return json.dumps({"H1": {"F01": 0.7}})
        out = propose_likelihoods(ev, caller=stub, batch_size=10)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(out[("H1", "F01")], 0.7)


class TestCheckpoints(unittest.TestCase):
    @staticmethod
    def _load_run_job():
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_job", ROOT / "scripts" / "run_job.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_save_load_and_mtime_invalidation(self):
        mod = self._load_run_job()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "candidates.json"
            mod.save_checkpoint(p, {"collected_mtime": 123.0,
                                    "candidates": [{"a": 1}]})
            got = mod.load_checkpoint(p, 123.0)
            self.assertEqual(got["candidates"], [{"a": 1}])
            self.assertIsNone(mod.load_checkpoint(p, 999.0))
            self.assertIsNone(mod.load_checkpoint(Path(td) / "nope.json",
                                                  123.0))


class TestMapCategories(unittest.TestCase):
    def test_valid_mapping_kept_invalid_dropped(self):
        ev = [{"evidence_id": "F01", "content": "警方悬赏20万元征集线索。"},
              {"evidence_id": "F02", "content": "法院判处死刑。"}]
        stub = lambda *a, **k: '{"F01": ["C13", "C99"], "F02": ["C18", "C19", "C20"], "F99": ["C01"]}'
        got = map_categories(ev, caller=stub)
        self.assertEqual(got["F01"], ["C13"])
        self.assertEqual(got["F02"], ["C18", "C19"])  # max 2 kept
        self.assertNotIn("F99", got)

    def test_invalid_json_returns_empty(self):
        ev = [{"evidence_id": "F01", "content": "x"}]
        self.assertEqual(
            map_categories(ev, caller=lambda *a, **k: "not json"), {})
    def _pack(self):
        items = extract_candidates(SOURCE_TEXT, "S01", "白银连环杀人案",
                                   caller=stub_caller)
        sources = [{"source_id": "S01", "title": "测试来源",
                    "publisher": "测试社", "published_at": "2016-08-29",
                    "url": "https://example.com/s01", "source_type": "news",
                    "is_reprint": False, "reprint_of": "", "origin_url": "",
                    "reliability": "", "last_verified": "", "notes": ""}]
        return build_draft_pack("CASE-DRAFT-TEST", "测试草稿案", "白银连环杀人案",
                                "job-test-1", sources, items,
                                [{"path": "web_search", "status": "found", "note": ""}],
                                likelihoods={("H1", "F01"): 0.95, ("H2", "F01"): 0.05})

    def test_grades_capped_at_c(self):
        pack = self._pack()
        self.assertTrue(all(e["grade"] == "C" for e in pack["evidence"]))
        self.assertTrue(all("A" not in e["grade"] and "B" not in e["grade"]
                            for e in pack["evidence"]))

    def test_hypotheses_uniform_priors_and_clamped_likelihoods(self):
        pack = self._pack()
        hyps = pack["case"]["hypotheses"]
        self.assertEqual(len(hyps), 5)
        self.assertTrue(all(h["prior"] == 0.2 for h in hyps))
        h1 = [h for h in hyps if h["hypothesis_id"] == "H1"][0]
        h2 = [h for h in hyps if h["hypothesis_id"] == "H2"][0]
        self.assertEqual(h1["likelihoods"]["F01"], 0.8)   # clamped from 0.95
        self.assertEqual(h2["likelihoods"]["F01"], 0.2)   # clamped from 0.05
        h3 = [h for h in hyps if h["hypothesis_id"] == "H3"][0]
        self.assertEqual(h3["likelihoods"]["F01"], 0.5)   # unmapped default

    def test_coverage_linked_by_category(self):
        pack = self._pack()
        c13 = [i for i in pack["coverage"]["items"] if i["item_id"] == "C13"][0]
        self.assertEqual(c13["evidence_ids"], ["F01"])
        c01 = [i for i in pack["coverage"]["items"] if i["item_id"] == "C01"][0]
        self.assertEqual(c01["evidence_ids"], [])

    def test_run_draft_end_to_end(self):
        pack = self._pack()
        with tempfile.TemporaryDirectory() as d:
            case_dir = write_draft_pack(Path(d) / "case", pack)
            out_dir = Path(d) / "reports"
            md_path, summary = run_draft(case_dir, out_dir)
            md = md_path.read_text(encoding="utf-8")
            self.assertTrue(md.startswith("# 草稿（未审）"))
            self.assertIn("未经人工复核", md)
            self.assertIn("资料覆盖", md)
            self.assertEqual(summary["bayes"]["verdict"].split(":")[0], "undecided")
            self.assertIsNotNone(summary["coverage"])
            self.assertEqual(summary["coverage"]["total"], 22)


if __name__ == "__main__":
    unittest.main()
