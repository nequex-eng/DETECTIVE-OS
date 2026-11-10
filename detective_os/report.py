"""DETECTIVE OS — report: every conclusion links back to its evidence."""
from __future__ import annotations


def render_markdown(case, ranking, bayes, plan, review, contra, sources):
    L = []
    L.append(f"# 案件分析报告：{case['name']}")
    L.append("")
    L.append(f"案件编号：{case['case_id']}｜状态：{case['status']}｜"
             f"公开资料数：{len(sources)}｜本报告只依据公开资料，不代表警方卷宗。")
    L.append("")
    L.append("## 结论（定性为主）")
    L.append("")
    if bayes:
        L.append(f"贝叶斯排序（先验与似然见档案，属模型排序，非破案概率）：{bayes['verdict']}。")
        for s in bayes["posteriors"]:
            L.append(f"- {s['hypothesis_id']}：后验{s['posterior']}（先验{s['prior']}）")
        L.append("")
        L.append(bayes["disclosure"])
    L.append("")
    L.append("定性打分（只计权重>0的证据）：")
    for hid, sc in ranking.items():
        L.append(f"- {hid}：支持{sc['support_weight']}，反对{sc['oppose_weight']}，"
                 f"净{sc['net']}，未解释{sc['unexplained']}项")
    L.append("")
    L.append("## 证据与来源")
    L.append("")
    L.append("每条结论均可回溯到证据编号，每条证据均可回溯到来源编号。")
    L.append("C级以下（网络传言、AI推断、待核实）不进入推理，见隔离清单。")
    L.append("")
    L.append("## 矛盾")
    L.append("")
    for c in contra:
        d = c.to_dict()
        L.append(f"- {d['contradiction_id']}（{d['type_label']}）："
                 f"{d['wording_a']} vs {d['wording_b']}。口径漂移可能：{d['could_be_drift']}。"
                 f"尚需：{d['needs_what']}。可解：{'是' if d['resolvable_now'] else '否'}。")
    L.append("")
    L.append("## 调查计划（下一步最值得查什么）")
    L.append("")
    for t in plan:
        L.append(f"- {t.task_id}：{t.question}｜目的：{t.purpose}｜"
                 f"价值：{t.estimated_value}｜渠道：{t.source_or_channel}")
    L.append("")
    L.append("## 独立审查")
    L.append("")
    L.append(f"审查发现{len(review['findings'])}条，其中 blocker {review['blockers']}条，"
             f"审查通过：{'是' if review['passed'] else '否'}。")
    for f in review["findings"]:
        L.append(f"- [{f['role']}/{f['severity']}] {f['finding']}")
    L.append("")
    L.append("## 本报告回答不了的问题")
    L.append("")
    L.append("公开资料无法回答：警方掌握但未公布的证据、法医原始报告、"
             "完整的排查记录、DNA比对现状。不得据此假装还原完整刑侦卷宗。")
    return "\n".join(L) + "\n"
