#!/usr/bin/env python3
"""Validate the Baiyin case pack against ground truth (kept separate).

The engine NEVER sees ground-truth.json. This script runs the engine on
pre-arrest public facts only, then scores each dimension:
  D1 single vs multiple perpetrators
  D2 long-term local presence vs drifter
  D3 stranger stalking vs acquaintance targeting
  D4/D5 motive and cessation: not modeled, reported as gaps.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.cli import load_case  # noqa: E402


def main():
    case_dir = ROOT / "cases" / "case-cn-1988-001"
    loaded = load_case(case_dir)
    bayes = loaded["hypotheses"].bayesian()
    post = {s["hypothesis_id"]: s["posterior"] for s in bayes["posteriors"]}
    ranked = [s["hypothesis_id"] for s in bayes["posteriors"]]
    gt = json.loads((case_dir / "ground-truth.json").read_text(encoding="utf-8"))

    checks = []
    single = post["H1"] + post["H2"]
    multi = post["H3"] + post["H5"]
    checks.append(("D1 单人作案", single > multi,
                   f"单人H1+H2={single:.4f} vs 多人/独立H3+H5={multi:.4f}"))
    checks.append(("D2 长期活动于白银", post["H1"] > post["H2"],
                   f"H1长期本地={post['H1']:.4f} vs H2外来流窜={post['H2']:.4f}"))
    stranger = post["H1"] + post["H2"]
    checks.append(("D3 尾随陌生人作案", stranger > post["H4"],
                   f"陌生人尾随H1+H2={stranger:.4f} vs 熟人针对H4={post['H4']:.4f}"))
    checks.append(("D1b H1排名第一", ranked[0] == "H1",
                   f"排名：{' > '.join(ranked)}"))
    checks.append(("D1c 独立案件假设垫底", ranked[-1] == "H5",
                   f"H5={post['H5']:.4f}（同一人DNA证据应将其压至最低）"))
    print(f"verdict: {bayes['verdict']}")
    for s in bayes["posteriors"]:
        print(f"  {s['posterior']:.4f}  {s['hypothesis_id']} (prior {s['prior']})")
    passed = 0
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        passed += ok
    print(f"score: {passed}/{len(checks)}")
    print("D4 动机、D5 停手原因：引擎未建模，记为缺口G2，不打分。")
    print("ground truth（校验用，不进入推理）："
          f"{gt['verdict']['perpetrator']}，{gt['verdict']['arrested']}，"
          f"{gt['verdict']['key_breakthrough']}。")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
