# T1 运行2报告（失败，实测记录）

- 运行：nequexkaggle/detective-os-t4，版本2
- 推送：2026-11-10 12:52:16 UTC；状态ERROR（12:57:24 UTC查到）；内核本身运行约109秒
- 运行地址：https://www.kaggle.com/code/nequexkaggle/detective-os-t4

## 预检：通过

2张Tesla T4，`preflight.json`与运行1一致。

## 实验1：通过

- 阈值0.60校准有效：聚类[[0,1,2,3,4,5,6,7,8,9],[10],[11],[12]]
- 10个转载聚为恰好1类，3条不同事实各自独立
- 转载两两最小相似度0.66835，跨事实最大相似度0.44566（与运行1完全一致，embedding确定性）
- 卸载验证通过：GPU0可用显存14.32GB→14.41GB
- `exp1_dedup.json`：pass=true

## 分词器烟雾测试：通过

- tokenizer OK：vocab=151643，tokens=25，解码回环保留原文

## 实验2：失败——Notebook验证行写错，不是模型问题

- 模型加载本身成功（约40秒完成下载+加载，无报错）
- 失败点：`llm.hf_device_map`报AttributeError——单设备device_map（{'': 'cuda:1'}）时transformers不挂hf_device_map属性
- 实验2的事实抽取、实验3、CPU复算均未运行
- 另：`torch_dtype`参数已废弃（仅警告，改用`dtype`）

## 额度消耗

内核约109秒，约0.06 GPU小时（按时间戳推算，约数）。运行1+运行2合计约0.11 GPU小时。

## 修复（已用于运行3）

- 设备验证改查参数实际所在设备：`set(str(p.device) for p in llm.parameters())`——这是实际落位，比计划中的device_map更权威
- `torch_dtype=torch.float16`改为`dtype=torch.float16`
- 运行3待推送为版本3。

## 原始文件

- `preflight.json`、`exp1_dedup.json`、`detective-os-t4.log`（含完整traceback）
