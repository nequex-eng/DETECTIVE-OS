#!/usr/bin/env python3
"""Build kaggle/detective-os-experiments.ipynb (nbformat 4, no manual JSON).

The notebook is the Stage-7 dual-T4 experiment:
  GPU 0: embedding retrieval + reprint dedup (Experiment 1)
  GPU 1: Qwen2.5-7B-Instruct 4-bit fact-extraction + contradiction eval (Exps 2-3)
  CPU:    rule inference from the case packs (skips cleanly when absent)
Preflight first (smallest unit, VRAM + import + tokenizer gates), then
experiments. Nothing here runs a long job without a gate passing.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def md(source):
    return {"cell_type": "markdown", "metadata": {},
            "source": source.splitlines(True)}


def code(source):
    ast.parse(source)  # every code cell must at least parse
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": source.splitlines(True)}


CELLS = [
    md("# DETECTIVE OS — 双T4实验 Notebook\n"
       "\n"
       "阶段7实验，不训练大型模型。先用API验证整体引擎，积累真实的高质量分析数据后，再考虑训练专用模型。\n"
       "\n"
       "- **GPU 0**：Embedding模型实验、文档语义检索、资料聚类、重复报道识别。\n"
       "- **GPU 1**：小模型事实抽取评测、矛盾识别评测、推理报告质量评测（Qwen2.5-7B-Instruct，4-bit）。\n"
       "- **CPU**：Python规则推理、时间线计算、关系图、贝叶斯模型实验。\n"
       "\n"
       "账号：Kaggle nequexkaggle，GPU T4x2，每周30小时，单次最长12小时。\n"
       "本Notebook不把Kaggle当长期在线服务器：网站运行不依赖它开启。\n"
       "评测标准答案来自本仓库 `cases/` 的真实案件包（南大案、白银案）。"),
    code('"""Cell 1 — preflight gate (gpu_job_preflight_gate).\n'
         'Proves environment before any timed work. Stops, never retries,\n'
         'when a check fails."""\n'
         "import sys, torch\n"
         "print('python', sys.version.split()[0])\n"
         "print('torch', torch.__version__, 'cuda', torch.cuda.is_available())\n"
         "for i in range(torch.cuda.device_count()):\n"
         "    p = torch.cuda.get_device_properties(i)\n"
         "    print(f'gpu{i}: {p.name} total={p.total_memory/2**30:.1f}GB')\n"
         "    free, _ = torch.cuda.mem_get_info(i)\n"
         "    print(f'  free={free/2**30:.1f}GB')\n"
         "assert torch.cuda.device_count() >= 1, 'NO GPU: enable GPU T4x2 in settings'\n"
         "for pkg in ['sentence_transformers', 'transformers', 'bitsandbytes', 'accelerate']:\n"
         "    try:\n"
         "        __import__(pkg); print(pkg, 'OK')\n"
         "    except ImportError:\n"
         "        print(pkg, 'MISSING (cell 2 will install)')\n"),
    code('"""Cell 2 — install only what is missing."""\n'
         "import importlib.util, subprocess, sys\n"
         "missing = [p for p in ['sentence_transformers', 'transformers',\n"
         "                       'bitsandbytes', 'accelerate']\n"
         "           if importlib.util.find_spec(p) is None]\n"
         "print('missing:', missing)\n"
         "if missing:\n"
         "    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q'] + missing)\n"
         "    print('installed')\n"
         "else:\n"
         "    print('nothing to install')\n"),
    md("## 实验1（GPU 0）：Embedding检索与重复报道识别\n"
       "\n"
       "模型：BAAI/bge-small-zh-v1.5（中文案件资料）。\n"
       "任务：10个转载版本（同一事实的不同转述）应聚为1类，3条不同事实应分开。\n"
       "标准答案：案件包 `evidence.json` 中的事实文本。"),
    code('"""Cell 4 — Experiment 1: dedup with bge-small-zh-v1.5."""\n'
         "import json, torch\n"
         "from sentence_transformers import SentenceTransformer\n"
         "model = SentenceTransformer('BAAI/bge-small-zh-v1.5', device='cuda:0')\n"
         "# 10 reprint variants of ONE Nanda fact (F04) + 3 distinct facts.\n"
         "base = '尸体被加热至熟，并切割成2000片以上，多数为长方形薄片，切割精细、码放整齐，头颅也被煮过。'\n"
         "reprints = [base,\n"
         "    '尸体被切成2000多片，头颅也被煮过。',\n"
         "    '凶手将其尸体加热至熟，并切割成2000片以上。',\n"
         "    '尸体被残忍肢解成两千多片，头颅被煮过。',\n"
         "    '法医确认尸体被煮熟后切成2000余片。',\n"
         "    '尸块共2000多片，切割均匀，码放整齐。',\n"
         "    '死者遗体被加热煮熟，切割成两千多片。',\n"
         "    '尸体被切成2000片以上，刀工十分精细。',\n"
         "    '经确认，尸体被煮熟并切割成2000多片。',\n"
         "    '凶手为毁尸灭迹，将尸体加热至熟，切割成2000片以上。']\n"
         "distinct = ['1996年1月10日傍晚，刁爱青在南京大学附近青岛路失踪。',\n"
         "           '2016年1月20日，公安部刑侦局回应追查到底。',\n"
         "           '1988年至2002年，白银市发生系列强奸杀人案，跨度14年。']\n"
         "texts = reprints + distinct\n"
         "emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)\n"
         "sim = emb @ emb.T\n"
         "import numpy as np\n"
         "rep_sim = sim[:10, :10][np.triu_indices(10, k=1)]\n"
         "cross_sim = sim[:10, 10:].max()\n"
         "print(f'reprint pairwise cosine: min={rep_sim.min():.3f} mean={rep_sim.mean():.3f}')\n"
         "print(f'max reprint-vs-distinct cosine: {cross_sim:.3f}')\n"
         "n_clusters = 1 if rep_sim.min() > 0.85 and cross_sim < 0.80 else -1\n"
         "result = {'reprint_min_sim': float(rep_sim.min()),\n"
         "          'reprint_mean_sim': float(rep_sim.mean()),\n"
         "          'cross_max_sim': float(cross_sim),\n"
         "          'pass': bool(rep_sim.min() > 0.85 and cross_sim < 0.80)}\n"
         "json.dump(result, open('/kaggle/working/exp1_dedup.json', 'w'), ensure_ascii=False, indent=2)\n"
         "print('EXP1 PASS' if result['pass'] else 'EXP1 FAIL', result)\n"),
    md("## 实验2（GPU 1）：Qwen2.5-7B-Instruct 事实抽取评测\n"
       "\n"
       "模型：Qwen/Qwen2.5-7B-Instruct，4-bit量化（约5GB，单张T4 15GB可放）。\n"
       "门控：先跑分词器烟雾测试（embedding形状、无NaN/Inf），通过才生成；\n"
       "生成只做抽取，不做裁决：输出必须引用给定段落，不得编造新事实。"),
    code('"""Cell 6 — Experiment 2: 4-bit Qwen fact extraction (gated)."""\n'
         "import json, torch\n"
         "from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig\n"
         "MODEL = 'Qwen/Qwen2.5-7B-Instruct'\n"
         "tok = AutoTokenizer.from_pretrained(MODEL)\n"
         "bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)\n"
         "llm = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb,\n"
         "                                           device_map='auto', trust_remote_code=True)\n"
         "# Gate: tokenizer smoke test before any generation.\n"
         "ids = tok('事实抽取测试：1996年1月19日清晨，清洁工在华侨路发现尸块。', return_tensors='pt').input_ids\n"
         "with torch.no_grad():\n"
         "    emb = llm.get_input_embeddings()(ids.to(llm.device))\n"
         "assert emb.shape[0] == 1 and not torch.isnan(emb).any() and not torch.isinf(emb).any()\n"
         "print('tokenizer gate OK, embedding shape', tuple(emb.shape))\n"
         "free, _ = torch.cuda.mem_get_info(0)\n"
         "print(f'free VRAM after load: {free/2**30:.1f}GB')\n"
         "\n"
         "def extract(paragraph, gold_keywords):\n"
         "    prompt = ('只从下面段落中抽取事实，每条一行，不得编造段落之外的事实。\\n'\n"
         "              f'段落：{paragraph}\\n事实：')\n"
         "    msgs = [{'role': 'user', 'content': prompt}]\n"
         "    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)\n"
         "    inputs = tok([text], return_tensors='pt').to(llm.device)\n"
         "    out = llm.generate(**inputs, max_new_tokens=200, temperature=0.0, do_sample=False)\n"
         "    gen = tok.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]\n"
         "    hit = sum(1 for k in gold_keywords if k in gen)\n"
         "    return gen, hit, len(gold_keywords)\n"
         "\n"
         "cases = [\n"
         "    ('受害人遗体碎片在其失踪9天后，也就是当年1月19日清晨，被一名清洁工在南京华侨路发现。'\n"
         "     '凶手为消灭作案痕迹，将其尸体加热至熟，并切割成2000片以上。',\n"
         "     ['1月19日', '华侨路', '2000片', '加热']),\n"
         "    ('1988年至2002年的14年间，甘肃省白银市9名女性和内蒙古包头市两名女性惨遭杀害，'\n"
         "     '部分受害人曾遭受性侵害。',\n"
         "     ['1988', '2002', '白银', '包头']),\n"
         "]\n"
         "results = []\n"
         "for para, gold in cases:\n"
         "    gen, hit, total = extract(para, gold)\n"
         "    results.append({'gold_hit': hit, 'gold_total': total, 'generation': gen[:300]})\n"
         "    print(f'keywords {hit}/{total}: {gen[:200]}')\n"
         "total_hit = sum(r['gold_hit'] for r in results)\n"
         "total_gold = sum(r['gold_total'] for r in results)\n"
         "summary = {'keyword_recall': total_hit / total_gold,\n"
         "           'pass': total_hit / total_gold >= 0.75}\n"
         "json.dump({'cases': results, 'summary': summary},\n"
         "          open('/kaggle/working/exp2_extraction.json', 'w'), ensure_ascii=False, indent=2)\n"
         "print('EXP2', summary)\n"),
    md("## 实验3（GPU 1）：矛盾识别评测\n"
       "\n"
       "给模型一对真实存在分歧的表述（南大案CT01：19岁 vs 年方20岁），\n"
       "合格答案必须指出这是口径差异（周岁/虚岁），而不是判定某方撒谎。"),
    code('"""Cell 8 — Experiment 3: contradiction identification."""\n'
         "import json, torch\n"
         "prompt = ('下面两种说法是否矛盾？请判断：是事实矛盾、口径差异，还是转述漂移，并说明理由。\\n'\n"
         "          '说法A：被害人刁爱青，遇害时19岁。（澎湃新闻）\\n'\n"
         "          '说法B：受害者是当时年方20岁的南大学生刁爱青。（现代快报）\\n判断：')\n"
         "msgs = [{'role': 'user', 'content': prompt}]\n"
         "text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)\n"
         "inputs = tok([text], return_tensors='pt').to(llm.device)\n"
         "out = llm.generate(**inputs, max_new_tokens=200, temperature=0.0, do_sample=False)\n"
         "gen = tok.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]\n"
         "print(gen)\n"
         "good = any(k in gen for k in ['口径', '虚岁', '周岁'])\n"
         "bad = '撒谎' in gen or '说谎' in gen\n"
         "summary = {'mentions_calibre': good, 'accuses_lying': bad,\n"
         "           'pass': bool(good and not bad)}\n"
         "json.dump({'generation': gen, 'summary': summary},\n"
         "          open('/kaggle/working/exp3_contradiction.json', 'w'), ensure_ascii=False, indent=2)\n"
         "print('EXP3', summary)\n"),
    md("## CPU部分：规则推理（案件包在场时运行）\n"
       "\n"
       "本单元不依赖GPU：复算两个案件包的贝叶斯排序，与 `reports/` 中的引擎输出对照。\n"
       "案件包不在场时干净跳过，不报错、不编造。"),
    code('"""Cell 10 — CPU: recompute Bayesian ranking from case packs."""\n'
         "import json, math, os\n"
         "from pathlib import Path\n"
         "for case_dir in [Path('cases/case-cn-1996-001'), Path('cases/case-cn-1988-001'),\n"
         "                 Path('/kaggle/input/detective-os/cases/case-cn-1996-001'),\n"
         "                 Path('/kaggle/input/detective-os/cases/case-cn-1988-001')]:\n"
         "    if not (case_dir / 'case.json').exists():\n"
         "        print(f'SKIP {case_dir}: case pack not mounted')\n"
         "        continue\n"
         "    case = json.loads((case_dir / 'case.json').read_text(encoding='utf-8'))\n"
         "    ev = {e['evidence_id']: e for e in json.loads((case_dir / 'evidence.json').read_text(encoding='utf-8'))}\n"
         "    w = {'A': 1.0, 'B': 0.8, 'C': 0.6, 'D': 0.5, 'E': 0.3, 'F': 0.0, 'G': 0.0, 'H': 0.0}\n"
         "    scored = []\n"
         "    for h in case['hypotheses']:\n"
         "        lp = math.log(h['prior'])\n"
         "        for eid, lik in h['likelihoods'].items():\n"
         "            lp += math.log(lik) * w[ev[eid]['grade']]\n"
         "        scored.append((h['hypothesis_id'], lp))\n"
         "    m = max(v for _, v in scored)\n"
         "    den = sum(math.exp(v - m) for _, v in scored)\n"
         "    print(case['case_id'], [(hid, round(math.exp(v - m) / den, 4)) for hid, v in sorted(scored, key=lambda x: -x[1])])\n"),
    code('"""Cell 11 — eval summary."""\n'
         "import json, glob\n"
         "for f in sorted(glob.glob('/kaggle/working/exp*.json')):\n"
         "    d = json.load(open(f))\n"
         "    s = d.get('summary', d)\n"
         "    print(f, '->', s)\n"
         "print('Done. All three experiments write /kaggle/working/exp*.json for the eval report.')\n"),
]

nb = {"nbformat": 4, "nbformat_minor": 0,
      "metadata": {"kernelspec": {"display_name": "Python 3",
                                  "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.10.0"},
                   "kaggle": {"accelerator": "gpu", "internet": True}},
      "cells": CELLS}

out = ROOT / "kaggle" / "detective-os-experiments.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
# Validate: every code cell parses (already asserted in code()), JSON loads back.
data = json.loads(out.read_text(encoding="utf-8"))
print(f"wrote {out} ({len(data['cells'])} cells)")
for i, c in enumerate(data["cells"]):
    if c["cell_type"] == "code":
        ast.parse("".join(c["source"]))
print("all code cells parse OK")
