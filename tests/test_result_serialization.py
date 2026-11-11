"""Result payload serialization tests for the auto-run executor."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "detective_os_run_job", ROOT / "scripts" / "run_job.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestPlanTaskSerialization(unittest.TestCase):
    def test_plan_tasks_are_json_safe_and_keep_all_user_relevant_fields(self):
        task = SimpleNamespace(
            task_id="T01", case_id="CASE-DRAFT-X",
            question="寻找第二个独立来源", purpose="验证单来源事实",
            hypotheses=["H1", "H3"], expected_info="独立来源",
            impact_if_yes="事实升级", impact_if_no="事实降级",
            source_or_channel="公开报道", estimated_value="high",
            status="open")
        got = MODULE.serialize_plan_tasks([task])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["task_id"], "T01")
        self.assertEqual(got[0]["hypotheses"], ["H1", "H3"])
        self.assertEqual(got[0]["impact_if_no"], "事实降级")
        self.assertEqual(got[0]["status"], "open")

    def test_empty_plan_is_an_empty_array(self):
        self.assertEqual(MODULE.serialize_plan_tasks([]), [])

    def test_timeline_uses_only_dates_visible_in_verbatim_quotes(self):
        events = MODULE.build_timeline_events([
            {"evidence_id": "F01", "source_id": "S01",
             "content": "刁爱青于当日失踪。", "original_quote": "1996年1月10日傍晚，刁爱青失踪。"},
            {"evidence_id": "F02", "source_id": "S02",
             "content": "警方在该时间段确认身份。", "original_quote": "1996年1月20日至31日，警方确认死者身份。"},
            {"evidence_id": "F03", "source_id": "S03",
             "content": "没有明确日期。", "original_quote": "警方后来继续调查。"},
        ])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["time"]["kind"], "date")
        self.assertEqual(events[0]["time"]["label"], "1996-01-10")
        self.assertEqual(events[1]["time"]["kind"], "range")
        self.assertIn("1996-01-20", events[1]["time"]["label"])
        self.assertEqual(events[0]["evidence_ids"], ["F01"])

    def test_traceability_graph_only_links_existing_source_ids(self):
        graph = MODULE.build_traceability_graph(
            [{"source_id": "S01", "title": "公开报道"}],
            [{"evidence_id": "F01", "source_id": "S01",
              "content": "事实", "grade": "C"},
             {"evidence_id": "F02", "source_id": "MISSING",
              "content": "无来源事实", "grade": "H"}])
        self.assertEqual(len(graph["entities"]), 3)
        self.assertEqual(len(graph["relationships"]), 1)
        self.assertEqual(graph["relationships"][0]["from"], "EVD-F01")
        self.assertEqual(graph["relationships"][0]["to"], "SRC-S01")


if __name__ == "__main__":
    unittest.main()
