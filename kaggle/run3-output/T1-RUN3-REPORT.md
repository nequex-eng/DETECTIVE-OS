# T1 运行3报告（失败，实测记录）

- 运行：nequexkaggle/detective-os-t4，版本3
- 推送：2026-11-10 12:58:16 UTC；状态ERROR（13:03:21 UTC查到）；内核本身运行约128秒
- 运行地址：https://www.kaggle.com/code/nequexkaggle/detective-os-t4

## 预检：通过

2张Tesla T4，`preflight.json`与运行1、2一致。

## 实验1：通过

- 阈值0.60：聚类[[0,1,2,3,4,5,6,7,8,9],[10],[11],[12]]
- 10个转载聚为恰好1类，3条不同事实各自独立
- 转载两两最小相似度0.66835，跨事实最大相似度0.44566
- 卸载验证通过：GPU0可用显存14.32GB→14.41GB

## 分词器烟雾测试：通过

tokenizer OK：vocab=151643，tokens=25，解码回环保留原文。

## 实验2：通过

- 模型：unsloth/Qwen2.5-7B-Instruct-bnb-4bit，设备验证改查参数实际所在设备后通过（`cuda:1`）
- 事实抽取：两段关键词召回8/8，recall=1.0
- 生成内容逐条核对无编造：南大段抽出1月19日、华侨路、2000片、加热；白银段抽出1988、2002、白银、包头
- `exp2_extraction.json`：pass=true

## 实验3：通过

- 模型复用实验2同一加载，未重载
- CT01（19岁 vs 年方20岁）：回答指出“口径差异”，未判定撒谎
- 卸载验证通过：GPU1可用显存回到14.41GB
- `exp3_contradiction.json`：pass=true

## CPU复算：顺序全对，数值差6.1e-05，断言失败

- 两案排序与参考完全一致（order_match=true）
- 数值差：白银案最大6.13e-05，南大案最大2.14e-05，均超过断言阈值1e-9
- 根因（本地复现确认）：引擎`reasoning.py`的`bayesian()`在softmax之前把对数后验四舍五入到4位小数，复算格跳过了这步。本地验证：引擎与存量报告差值0.0（报告是现行的，不是旧的）；复算格补上`round(lp, 4)`和`round(posterior, 4)`后，与存量报告差值0.0、完全一致
- 不是引擎算错，也不是案件数据问题，是复算格没有逐字复现引擎的舍入步骤

## 额度消耗

内核约128秒，约0.07 GPU小时（按时间戳推算，约数）。运行1+2+3合计约0.18 GPU小时。

## 修复（已用于运行4）

复算格按引擎逐字复现舍入：`round(lp, 4)`再softmax，`round(posterior, 4)`再比对；阈值保持1e-9（补上舍入后本地差值为0.0）。运行4待推送为版本4。

## 原始文件

- `preflight.json`、`exp1_dedup.json`、`exp2_extraction.json`、`exp3_contradiction.json`、`exp_cpu_recompute.json`、`detective-os-t4.log`
- 注意：下载时把CPU格克隆的仓库副本（`detective-os/`目录，含.git）也一并拉下来了，那只是GitHub仓库在当时的快照，不是实验产物，写回仓库时不收录。
