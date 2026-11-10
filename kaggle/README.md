# Kaggle 双T4实验（阶段7，T1）

第一版不要训练大型模型。先用API验证整体引擎，积累真实的高质量分析数据后，再考虑训练专用模型。

## Notebook

`detective-os-experiments.ipynb`（13格，全部通过AST校验与8项静态检查）：

- 预检门（第1格）：要求恰好2张GPU、型号均为Tesla T4，记录每张卡的型号、总显存、可用显存，写入`preflight.json`；不是T4×2就停止，不烧额度。
- 依赖安装（第2格）：只装缺失的包。
- 实验1（GPU 0）：BAAI/bge-small-zh-v1.5，真实聚类（并查集，余弦相似度>0.85连边）：10个转载版本必须聚为恰好1类，3条不同事实必须各自独立成类；结果写入`exp1_dedup.json`，随后卸载模型并验证显存释放。
- 分词器烟雾测试（第6格）：只加载分词器，编码抽查、解码回环，通过后才加载大模型。
- 实验2（GPU 1）：unsloth/Qwen2.5-7B-Instruct-bnb-4bit（同一Qwen2.5-7B-Instruct权重，预量化4-bit，约5GB；不用官方仓库加load_in_4bit，避免下载约15GB全量权重再现量化的CPU内存峰值），显式`device_map={"": "cuda:1"}`，打印并断言实际设备分布；事实抽取评测，关键词召回≥0.75算通过；结果写入`exp2_extraction.json`。
- 实验3（GPU 1）：复用实验2已加载的同一模型，按顺序运行，不再加载第二份模型；南大案CT01（19岁 vs 年方20岁），合格答案必须指出口径差异（周岁/虚岁）、不得判定撒谎；结果写入`exp3_contradiction.json`，随后卸载模型并验证显存释放。
- CPU部分：从GitHub公开仓库浅克隆最新案件包与引擎报告，复算两个案件的贝叶斯排序，与报告中的参考后验逐项核对（顺序一致、数值差<1e-9），写入机器可读的`exp_cpu_recompute.json`；克隆失败或核对不符都记为失败，不静默跳过。
- 汇总格：读全部报告文件并打印对照表；任何一项失败都会让运行以失败告终并保留日志，绝不只打印PASS。

每个实验写`/kaggle/working/`下的评测报告：`preflight.json`、`exp1_dedup.json`、`exp2_extraction.json`、`exp3_contradiction.json`、`exp_cpu_recompute.json`。

## 推上Kaggle（T1已授权，消耗GPU额度）

```bash
cd kaggle
kaggle kernels push
```

注意：普通`kaggle kernels push`会启动运行，不要把它误认为只上传。推送前确认加速器为GPU T4x2、联网开启（见`kernel-metadata.json`：`enable_gpu`与`enable_internet`均为true；运行时的预检门会再次核验两张T4，不符即停）。

监控：`kaggle kernels status nequexkaggle/detective-os-experiments`，不要盲目重复启动。
下载报告：`kaggle kernels output nequexkaggle/detective-os-experiments -p <目录>`。

## 分工

- **GPU 0**：Embedding模型实验、文档语义检索、资料聚类、重复报道识别。
- **GPU 1**：小模型LoRA微调实验、结构化事实提取评测、矛盾识别评测、推理报告质量评测。
- **CPU**：Python规则推理、时间线计算、NetworkX关系图、数据清洗、贝叶斯模型实验。

## 账号

Kaggle账号nequexkaggle，GPU T4x2，每周30小时，单次最长12小时。
