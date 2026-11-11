# T1 运行4报告（全部通过，实测记录）

- 运行：nequexkaggle/detective-os-t4，版本4
- 推送：2026-11-10 13:06:04 UTC；状态COMPLETE（14:36:32 UTC查到）
- 内核运行约157秒；之前排队约90分钟（排队不耗GPU额度）
- 运行地址：https://www.kaggle.com/code/nequexkaggle/detective-os-t4

## 预检：通过

2张Tesla T4，各14.56GB总显存、14.46GB可用，torch 2.11.0+cu130。

## 实验1：通过

- 阈值0.60：聚类[[0,1,2,3,4,5,6,7,8,9],[10],[11],[12]]
- 10个转载聚为恰好1类，3条不同事实各自独立
- 转载两两最小相似度0.66835，跨事实最大相似度0.44566
- 卸载验证通过：GPU0可用显存14.32GB→14.41GB

## 分词器烟雾测试：通过

tokenizer OK：vocab=151643，tokens=25，解码回环保留原文。

## 实验2：通过

- 模型：unsloth/Qwen2.5-7B-Instruct-bnb-4bit，参数实际所在设备验证通过（`cuda:1`）
- 事实抽取：两段关键词召回8/8，recall=1.0
- 生成内容逐条核对无编造：南大段抽出1月19日、华侨路、2000片、加热；白银段抽出1988、2002、白银、包头
- `exp2_extraction.json`：pass=true

## 实验3：通过

- 模型复用实验2同一加载，未重载
- CT01（19岁 vs 年方20岁）：回答指出“口径差异”，未判定撒谎
- 卸载验证通过：GPU1可用显存回到14.41GB
- `exp3_contradiction.json`：pass=true

## CPU复算：通过（差值0.0）

- 两案排序与参考完全一致（order_match=true）
- 数值差：白银案0.0，南大案0.0
- 运行3的失败根因已验证修复：复算格按引擎逐字复现舍入（`round(lp, 4)`再softmax，`round(posterior, 4)`再比对）
- `exp_cpu_recompute.json`：pass=true

## 汇总格：通过

- `SUMMARY: [('preflight.json', True), ('exp1_dedup.json', True), ('exp2_extraction.json', True), ('exp3_contradiction.json', True), ('exp_cpu_recompute.json', True)]`
- `ALL EXPERIMENTS PASSED (measured, not printed)`

## 额度消耗

内核约157秒，约0.044 GPU小时（按时间戳推算，约数）。运行1+2+3+4合计约0.23 GPU小时。

## 原始文件

- `preflight.json`、`exp1_dedup.json`、`exp2_extraction.json`、`exp3_contradiction.json`、`exp_cpu_recompute.json`、`detective-os-t4.log`
- 注意：下载时把CPU格克隆的仓库副本（`detective-os/`目录，含.git）也一并拉下来了，已删除，那只是GitHub仓库在当时的快照，不是实验产物，写回仓库时不收录。
