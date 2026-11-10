# DETECTIVE OS — 交接任务书（给GPT）

> 适用对象：接手继续开发的AI（ChatGPT）。日期：2026-11-10。
> 先读完本文件，再读仓库README.md，然后动手。不要凭猜测补事实，不要把推测写成结论。

## 1. 项目一句话

DETECTIVE OS是针对真实历史刑事案件的公开资料研究、证据分析、竞争性假设推理与调查辅助系统。不是聊天网站，不是虚构推理游戏。第一版只做一件事：把公开资料排干净，算出假设的相对排序，指出还缺什么证据。

- GitHub：https://github.com/nequex-eng/DETECTIVE-OS（公开，main分支）
- 网站：https://detective-os.pages.dev（Cloudflare Pages，双案件版，已上线并实核）
- 本地工程：`~/workspace/detective-os/`（本文件也在仓库根目录）

## 2. 红线（不可违反）

1. 绝不把AI推测包装成事实；所有结论必须能点回证据与来源。
2. 绝不根据网络传言指认现实中的个人为凶手；被报道提及不等于嫌疑人。
3. 证据分级权重固定：A 1.0、B 0.8、C 0.6、D 0.5、E 0.3，F（网络传言）、G（AI推断）、H（尚待核实）一律0.0。AI推断永不升级为证据。
4. 贝叶斯输出必须公开先验、似然、来源与不确定性；前两名差距小于0.1时结论为“无法判断”，拒绝过早选定。
5. 公开资料回答不了的问题必须明说，不得假装还原完整刑侦卷宗。

## 3. 已完成状态（均已验证，不是计划）

| 部分 | 状态 | 验证 |
| --- | --- | --- |
| 核心引擎8模块（来源情报、同源识别、A-H证据分级、模糊时间线、关系图谱、5类矛盾、竞争性假设、调查计划、6角色独立审查） | 完成 | 纯Python标准库，14张表SQLite（D1兼容子集），行不原地覆盖，推理过程全记录 |
| 案件1 CASE-CN-1996-001 南大碎尸案 | 完成 | 8来源、28条证据（A7/B6/C5/D2/E1/F3/G1/H3）、9事件、11实体、5矛盾、5假设、8缺口 |
| 案件2 CASE-CN-1988-001 白银连环杀人案（回溯校验） | 完成 | 8来源、10条证据（A4/B4/C1/H1）、6事件、5实体、5矛盾、5假设、6缺口 |
| 验收测试 | 17项全过 | `tests/test_acceptance.py` 11项 + `tests/test_baiyin_validation.py` 6项 |
| GitHub | 已推送 | 4次快照提交，40个文件，最新提交8a6da8b |
| Pages静态站 | 已上线并实核 | `public/`由真实报告数据生成，`python3 scripts/build_site.py` |
| Kaggle双T4实验Notebook | 文件已建，未运行 | `kaggle/detective-os-experiments.ipynb`，12格，AST全过 |

## 4. 关键数字（已核验，引用时直接用）

- 南大案贝叶斯：H1熟人加专业技能44.30%、H3陌生人加专业技能43.29%、H5团伙6.21%、H2熟人无技能3.91%、H4陌生人无技能2.29%；前两名差0.0101，结论为无法判断；稳健结论只有一条：具备专业技能合计87.59%，无技能合计6.20%。
- 白银案贝叶斯：H1单人连环、长期活动于白银、尾随陌生年轻女性69.17%，H2单人连环、外来流窜26.56%，H3多人或模仿2.09%，H4熟人针对1.93%，H5多起独立案件0.25%；前两名差0.4261，结论为H1领先。校验5项全过（单人合计95.73%对多人/独立2.34%、H1高于H2、陌生人尾随合计95.73%对熟人针对1.93%、H1排名第一、独立案件假设垫底）。
- 白银案校验方法（关键）：引擎只读2016年8月25日之前的公开事实；抓获、DNA-Y比对、审判等事后信息只存在于独立的`cases/case-cn-1988-001/ground-truth.json`，不进入推理；测试强制检查证据文本不含凶手姓名、落网、DNA-Y。
- 南大案新确认：年龄19岁与“年方20岁”并存是周岁与虚岁口径差异；家属姐姐姓名在澎湃2016年采访中为化名，与中新网2021年“刁爱华”无法确认是否为同一人，不得混用；2022年5月30日南京警方回应“暂未侦破”。
- 白银案新发现5条报道间矛盾：部督年份2001年8月与2004年8月说法不一；重启侦查年份2015年3月与2016年3月说法不一；白银与包头分布9加2与10加1说法不一（总数11起一致）；作案时段白天与夜间说法不一；首案月份1988年5月与6月说法不一。均已并存记录，未强行取舍。

## 5. 仓库结构与命令

```
detective_os/   core.py（模块1-4）、reasoning.py（模块5-8）、db.py、report.py、cli.py
cases/case-cn-1996-001/   case.json、sources.json、evidence.json、events.json、entities.json、contradictions.json
cases/case-cn-1988-001/   同上，另有ground-truth.json（只用于校验，不进入推理）
tests/          test_acceptance.py、test_baiyin_validation.py
scripts/        build_site.py、build_notebook.py、validate_baiyin.py
kaggle/         detective-os-experiments.ipynb、kernel-metadata.json、README.md
public/         index.html、case-cn-1996-001.html、case-cn-1988-001.html（生成物，别手改）
deploy.py、wrangler.toml
```

```bash
python3 -m detective_os.cli check cases/case-cn-1996-001
python3 -m detective_os.cli run cases/case-cn-1996-001
python3 -m unittest discover -s tests
python3 scripts/validate_baiyin.py
python3 scripts/build_site.py
python3 deploy.py   # 部署Pages，wrangler direct upload
```

## 6. 未完成任务（按顺序做，每项做完要过验收）

### T1. Kaggle Notebook推上运行，出评测报告

- 文件已在`kaggle/`，推送命令见`kaggle/README.md`（`kaggle kernels push`，只上传定义、不耗额度）。
- 跑之前确认加速器为GPU T4x2、联网开启；账号nequexkaggle，每周30小时额度，单次最长12小时。
- Notebook结构：预检门（GPU数量与显存、分词器烟雾测试，不过就停）→实验1去重（BAAI/bge-small-zh-v1.5）→实验2事实抽取（Qwen2.5-7B-Instruct 4-bit，关键词召回≥0.75算通过）→实验3矛盾识别（南大案CT01，合格答案必须指出口径差异、不得判定撒谎）→CPU复算。
- 验收：三项实验的`/kaggle/working/exp*.json`评测报告齐全，写入仓库`kaggle/`并更新README；额度消耗如实记录。

### T2. 第三个案件（再选一起未侦破案件）

- 目的：检验引擎在没有已知答案时的表现（白银案是有答案的校验，南大案与第三案是无答案的实战）。
- 选案标准：公开资料丰富（≥2独立来源、≥1主流或官方）、有明确的矛盾点、不得涉及未成年人隐私细节。
- 做法：照抄案件1的建包流程（先实读来源、再分级证据、再写矛盾与假设）；每条事实都要有证据编号、原文引用、来源位置、可信度理由。
- 验收：`check`通过、测试新增该案的回归测试、报告生成、结论为无法判断时不得强行选定。

### T3. 前端工作站（React加TypeScript）

- 10个导航页：案件中心、来源库、证据板、时间线、关系图谱、矛盾实验室、假设实验室、调查计划、审查室、最终报告。
- 风格：专业深色研究工作站；每个结论可点击回溯到证据与来源。
- 数据来源：引擎报告JSON，不得手写假数据、不得做没有实际功能的模块名。

### T4. Workers API + D1 + R2

- Workers API提供案件包的读写接口；D1用本地SQLite的14张表结构（已按D1兼容子集设计）；R2存附件。
- 绑定必须写进`wrangler.toml`（部署会重写后台单独改的绑定），部署完再GET项目核验绑定还在。
- 验收：API返回的数据与本地报告一致；前端可切换线上线下数据源。

### T5. Provider Adapter（LLM接入）

- 可切换：MiniMax、OpenAI兼容接口、本地模型。LLM只干四件事：从资料里抽事实进档案、按假设库生成待验证的推论、逐条做反驳检验、把引擎的数字写成人能读的报告。
- 硬约束写进提示词：只许引用档案编号，不许编造新事实，不确定就写未知，数字必须来自引擎输出，LLM自己不许算概率。
- 验收：同一案件换Provider，引擎数字不变；LLM输出逐条可追溯。

### T6. 补1996年原始资料缺口G7、G8

- G7：1996年协查通报与认尸启示原始版面；G8：1996年2月至4月排查同期报道原文。
- 找不到就如实记为缺口，不得用二手转述升级为A级。

## 7. 行文与工程规则

- 中文与英文字母、数字、符号之间一律不加空格；日文同理；英文正文内部仍按英文正常词间空格写。适用于所有中文输出，包括网站、标题、报告。旧内容不回改。
- 改一处验一处：改引擎先跑`check`与全部测试，改案件包先跑`validate`，改网站先本地生成再部署；不报没有实测过的数字。
- 先验概率是主观起点：排序对先验敏感时，平先验下的排序须一并报告。
- 不要做的事：不要建新仓库（已建好）；不要用Muse的GitHub App调`create_repository`（会报403）；不要把`workers.dev`地址当作公开地址发布（建站一律走Pages，`xxx.pages.dev`）。
- GitHub推送：用快照推送流程（`git ls-files`生成清单文件、经`push-files`推送、保存同步记录），不要在聊天里索要或粘贴任何token、密码。

## 8. 交付物清单（每完成一项都要有）

1. 代码与案件包进仓库并推送，提交信息写清做了什么与验证结果。
2. README.md更新：模块状态、案件结果、测试结果、未完成事项。
3. 测试全过（`python3 -m unittest discover -s tests`），新功能要有新测试。
4. 网站有变化时重新生成`public/`并执行`python3 deploy.py`，上线后实核首页与相关页面能打开。
5. 本交接文件同步更新：已完成项移入第3节，未完成项更新状态。
