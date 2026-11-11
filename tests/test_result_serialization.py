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


if __name__ == "__main__":
    unittest.main()
