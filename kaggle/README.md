# Kaggle 双T4实验（阶段7）

第一版不要训练大型模型。先用API验证整体引擎，积累真实的高质量分析数据后，再考虑训练专用模型。

## Notebook

`detective-os-experiments.ipynb`（12格，全部通过AST校验）：

- 预检门（第1–2格）：GPU数量与显存、分词器烟雾测试，任何一项不过就停，不重试、不烧额度。
- 实验1（GPU 0）：BAAI/bge-small-zh-v1.5，10个转载版本聚为1类、3条不同事实分开；标准答案来自案件包证据文本。
- 实验2（GPU 1）：Qwen2.5-7B-Instruct 4-bit（约5GB），事实抽取评测，关键词召回≥0.75算通过；只抽取、不裁决，输出不得编造段落之外的事实。
- 实验3（GPU 1）：矛盾识别评测，南大案CT01（19岁 vs 年方20岁），合格答案必须指出口径差异（周岁/虚岁），不得判定某方撒谎。
- CPU部分：复算两个案件包的贝叶斯排序，与`reports/`对照；案件包不在场时干净跳过。

每个实验写`/kaggle/working/exp*.json`评测报告。

## 推上Kaggle（需用户点头，消耗GPU额度）

```bash
cd ~/workspace/detective-os/kaggle
kaggle kernels push
```

推送只上传定义，不跑、不耗额度。跑之前先在Kaggle设置里确认加速器为GPU T4x2、联网开启。预计三项实验合计不超过1小时，单次会话最长12小时。

## 分工

- **GPU 0**：Embedding模型实验、文档语义检索、资料聚类、重复报道识别。
- **GPU 1**：小模型LoRA微调实验、结构化事实提取评测、矛盾识别评测、推理报告质量评测。
- **CPU**：Python规则推理、时间线计算、NetworkX关系图、数据清洗、贝叶斯模型实验。

## 账号

Kaggle账号nequexkaggle，GPU T4x2，每周30小时，单次最长12小时。
