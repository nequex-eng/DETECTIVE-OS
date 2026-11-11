# DETECTIVE OS

真实刑事悬案推理引擎：公开资料研究、证据分析、竞争性假设推理、调查辅助系统。

不是聊天网站，不是虚构推理游戏。第一版只做一件事：把公开资料排干净，算出假设的相对排序，指出还缺什么证据，绝不把推测包装成事实，绝不根据网络传言指认现实中的个人为凶手。

## 接手任务书（给GPT）

接手的AI先读完本README，再动手。不要凭猜测补事实，不要把推测写成结论。

### 红线（不可违反）

1. 绝不把AI推测包装成事实；所有结论必须能点回证据与来源。
2. 绝不根据网络传言指认现实中的个人为凶手；被报道提及不等于嫌疑人。
3. 证据分级权重固定：A 1.0、B 0.8、C 0.6、D 0.5、E 0.3，F（网络传言）、G（AI推断）、H（尚待核实）一律0.0。AI推断永不升级为证据。
4. 贝叶斯输出必须公开先验、似然、来源与不确定性；前两名差距小于0.1时结论为“无法判断”，拒绝过早选定。
5. 公开资料回答不了的问题必须明说，不得假装还原完整刑侦卷宗。

### 已完成任务

**T1. Kaggle Notebook推上运行，出评测报告（2026-11-10已完成）。**运行地址：https://www.kaggle.com/code/nequexkaggle/detective-os-t4。共4次运行，版本4全部通过：预检（2张Tesla T4）→实验1去重通过（阈值0.60，10个转载聚为1类）→实验2事实抽取通过（关键词召回8/8=1.0，设备cuda:1）→实验3矛盾识别通过（CT01指出口径差异，未判定撒谎）→CPU复算通过（两案排序一致，数值差0.0）。失败记录：运行1实验1阈值0.85过严（改0.60）；运行2实验2死于hf_device_map验证行bug（改查参数实际所在设备）；运行3 CPU复算数值差6.1e-05（根因：引擎在softmax前把对数后验舍入到4位小数，复算格跳过了这步；补上舍入后差值0.0）。运行4排队约90分钟，内核约157秒。额度合计约0.23 GPU小时。报告在kaggle/run1-output/至run4-output/（每份含T1-RUN*-REPORT.md）。

**V1. 自动调查模式：前端输入调查方向即自动跑（2026-11-11已建成，端到端测试已完成，见下文“自动调查模式V1”与V0）。** intake页`public/investigate.html`→Pages Functions收请求写Cloudflare KV任务→定时跑手每10分钟轮询→`scripts/run_job.py`跑抽取、似然、映射、草稿包、引擎、报告→结果写回KV，前端轮询展示。红线已进代码：抽取证据最高C级、报告带“草稿（未审）”横幅、永不碰两个正式案包、不得按传言指认活人。端到端测试任务c23978f6（1988-2002白银连环杀人案重推）已完成：9个来源、63条事实全C级、结论H3陌生人加技能领先52.45%、覆盖率31.8%、审查6个blocker；断点续跑检查点已生效（两次虚拟机重启未丢进度）。

### 未完成任务（按顺序做，每项做完要过验收）

**V0. 跑完端到端测试并收尾（2026-11-11已完成）。**任务c23978f6-56f1-4789-b488-b36c4b9117a7（方向“1988-2002白银连环杀人案”，语言zh，地区中国甘肃白银）。实测结果：9个来源（3中文加6英文/维基）、63条事实全C级、似然315对、覆盖映射18条；结论H3陌生人加技能领先52.45%（H1 25.66%、H4 13.56%、H2 8.17%、H5 0.16%，前两名差0.2679），覆盖率31.8%（4项已覆盖/6项单来源/12项缺失，共22项），独立审查6个blocker；报告带草稿横幅，`reports/CASE-DRAFT-c23978f6-report.md`，前端`investigate.html`可见done。注意：草稿的H3（陌生人加技能）与手工白银案包的H1（单人连环、本地、尾随陌生女性）指向一致，都是陌生人加技能方向；手工包H1 69.17%是另一套假设定义下的数，两者不可直接比大小。收尾余项（不阻塞T2）：删KV里残留的`probe-direct`探针键（走REST DELETE，不要用wrangler kv命令）；把定时任务`detective-os-job-watch`的正文改成调`scripts/run_job.py <job_id>`（现正文是run_job.py出现之前的旧版分步描述；改前`cron.view`读全文，改后`cron.view`读回确认）。

**T2. 第三个案件（再选一起未侦破案件）。**目的：检验引擎在没有已知答案时的表现（白银案是有答案的校验，南大案与第三案是无答案的实战）。选案标准：公开资料丰富（≥2独立来源、≥1主流或官方）、有明确的矛盾点、不得涉及未成年人隐私细节。做法：照抄案件1的建包流程（先实读来源、再分级证据、再写矛盾与假设）；每条事实都要有证据编号、原文引用、来源位置、可信度理由。验收：`check`通过、测试新增该案的回归测试、报告生成、结论为无法判断时不得强行选定。

**T3. 前端工作站（React加TypeScript）。**10个导航页：案件中心、来源库、证据板、时间线、关系图谱、矛盾实验室、假设实验室、调查计划、审查室、最终报告。风格：专业深色研究工作站；每个结论可点击回溯到证据与来源。数据来源：引擎报告JSON，不得手写假数据、不得做没有实际功能的模块名。

**T4. Workers API + D1 + R2。**Workers API提供案件包的读写接口；D1用本地SQLite的14张表结构（已按D1兼容子集设计）；R2存附件。绑定必须写进`wrangler.toml`（部署会重写后台单独改的绑定），部署完再GET项目核验绑定还在。验收：API返回的数据与本地报告一致；前端可切换线上线下数据源。

**T5. Provider Adapter（LLM接入）。**可切换：MiniMax、OpenAI兼容接口、本地模型。LLM只干四件事：从资料里抽事实进档案、按假设库生成待验证的推论、逐条做反驳检验、把引擎的数字写成人能读的报告。硬约束写进提示词：只许引用档案编号，不许编造新事实，不确定就写未知，数字必须来自引擎输出，LLM自己不许算概率。验收：同一案件换Provider，引擎数字不变；LLM输出逐条可追溯。

**T6. 补1996年原始资料缺口G7、G8。**G7：1996年协查通报与认尸启示原始版面；G8：1996年2月至4月排查同期报道原文。找不到就如实记为缺口，不得用二手转述升级为A级。

### 行文与工程规则

- 中文与英文字母、数字、符号之间一律不加空格；日文同理；英文正文内部仍按英文正常词间空格写。适用于所有中文输出，包括网站、标题、报告。旧内容不回改。
- 改一处验一处：改引擎先跑`check`与全部测试，改案件包先跑`validate`，改网站先本地生成再部署；不报没有实测过的数字。
- 先验概率是主观起点：排序对先验敏感时，平先验下的排序须一并报告。
- 不要做的事：不要建新仓库（已建好）；不要用Muse的GitHub App调`create_repository`（会报403）；不要把`workers.dev`地址当作公开地址发布（建站一律走Pages，`xxx.pages.dev`）。
- GitHub推送：用快照推送流程（`git ls-files`生成清单文件、经`push-files`推送、保存同步记录），不要在聊天里索要或粘贴任何token、密码。

### 交付物清单（每完成一项都要有）

1. 代码与案件包进仓库并推送，提交信息写清做了什么与验证结果。
2. 本README更新：模块状态、案件结果、测试结果、未完成事项；已完成项移入正文，任务状态同步更新。
3. 测试全过（`python3 -m unittest discover -s tests`），新功能要有新测试。
4. 网站有变化时重新生成`public/`并执行`python3 deploy.py`，上线后实核首页与相关页面能打开。

## 快速开始

```bash
python3 -m detective_os.cli check cases/case-cn-1996-001
python3 -m detective_os.cli run cases/case-cn-1996-001
python3 -m unittest discover -s tests -v
```

只用Python标准库，无第三方依赖。推理计算在本地跑，网站正常运行不依赖Kaggle Notebook。

## 架构

```
detective_os/
  core.py       模块1-4：来源登记、证据板、时间线、关系图谱
  reasoning.py  模块5-8：矛盾检测、假设推理、调查计划、独立审查
  coverage.py   模块9：资料覆盖清单（通用模板、独立来源判定、覆盖率计算）
  llm.py        MiniMax-M3调用（抽取专用，重试5次）
  pipeline.py   自动调查管线：查询规划、抽取、似然拟合、覆盖映射、草稿包
  db.py         SQLite结构（14张表，D1兼容子集），版本管理加审计日志
  report.py     带引用的分析报告生成
  cli.py        命令行入口（run/check/coverage）
functions/api/investigate.js  POST /api/investigate：建任务写KV
functions/api/jobs.js         GET /api/jobs：读任务（只读）
scripts/job.py      跑手任务工具：poll/get/update（KV走REST API）
scripts/run_job.py  单任务执行器：抽取→似然→映射→草稿包→引擎→回写
public/investigate.html  自动调查 intake 页
cases/case-cn-1996-001/   首个案件包：南大碎尸案（含coverage.json）
tests/test_acceptance.py  验收测试1-10
tests/test_coverage.py    覆盖清单测试14项
tests/test_pipeline.py    管线测试17项（抽取、似然分批、映射、检查点、草稿包）
```

前端（React加TypeScript）、Cloudflare Workers API、D1、R2、Kaggle双T4实验Notebook按阶段推进，不在本版。

## 九个模块，全部实际运行

1. **来源情报**：每个资料记来源、作者、时间、原始链接、是否转载、是否找到原始出处、可信度、最后核验时间。同源识别：转载链按原始出处归一，20篇转载同一个未经证实的消息只算1个独立来源。
2. **证据管理**：八级分级。A已确认事实，B权威机构公开信息，C媒体采访或报道，D当事人或证人陈述，E第三方转述，F网络传言，G AI推断，H尚待核实。权重：A 1.0、B 0.8、C 0.6、D 0.5、E 0.3、F/G/H 0.0。AI推断永不升级为证据，代码里直接拒绝。
3. **时间线**：时间精度分五级（精确、日期、范围、大致、未知），“傍晚”保留为“傍晚”，不编造小时；自动检测空白区间。
4. **关系图谱**：人物、地点、事件、证据、机构、物品、时间、假设八类节点，每条关系必须有来源。被报道提及不等于嫌疑人；标记嫌疑人须A/B级依据，否则代码拒绝。
5. **矛盾检测**：五种类型（时间、陈述、媒体间、物证、逻辑）。每条矛盾输出编号、原文引用、两种说法、口径漂移可能、尚需资料、是否可解。细节差异不自动判定为撒谎。
6. **假设推理**：多竞争性假设，每个带支持、反对、未解释事实、必要前提、可验证预测、可证伪点。默认定性打分；贝叶斯为可选项，先验、似然、来源、不确定性全部公开。前两名差距小于0.1时结论为“无法判断”，拒绝过早选定。
7. **调查计划**：按价值排序下一步查什么：单来源主张、未解矛盾、无法区分的假设对优先。
8. **独立审查**：六个角色（资料、时间线、证据、假设、反方、最终审查）。反方必须引用反证，否则审查自检失败；最终审查检查逻辑跳跃、循环论证、错误归因、无来源断言。
9. **资料覆盖清单**（2026-11-10新增，用户令先做本模块再选第三案）：通用冷案模板10类22项（失踪/案发、发现、身份确认、法医/物证、侦查过程、作案手法、动机、法律程序、家属与当事人、官方回应），每项挂证据编号与已尝试的收集路径（网上搜索、直接读源头、新闻数据库、网页档案、法院数据库、本地语言搜索、书/纪录片/播客、用户供料、线索社区、信息公开申请）。覆盖只计权重>0的证据（A–E级），传言、AI推断、待核实不计入；“已覆盖”须≥2个独立来源（转载链归一后计数），1个为单来源，0个为缺失。覆盖率=（已覆盖+0.5×单来源）/适用项。缺失是事实不是失败；公开资料永远无法覆盖警方未公开的证据，本数只针对已定义的清单。用法规：`python -m detective_os.cli coverage cases/case-cn-1996-001`；报告含“资料覆盖”章节，`check`会校验coverage.json。

## 数据库

14张表：cases、sources、evidence、events、persons、entities、relationships、hypotheses、hypothesis_evidence、contradictions、investigation_tasks、investigation_results、reasoning_runs、audit_logs。行不原地覆盖：更新产生新版本加审计记录；每次推理记录所用证据、模型、提示词版本、输出与结论，结论被推翻时旧版本保留。

## 首个案件：CASE-CN-1996-001

1996南京大学刁爱青遇害案。8个来源（新华网、澎湃新闻、中国新闻网、新京报、扬子晚报引述、英文维基交叉核对），28条证据（A 7、B 6、C 5、D 2、E 1、F 3、G 1、H 3），9个事件，11个实体，5条矛盾，5个竞争性假设，8个缺口。

本轮跑出的结论：贝叶斯排序H1熟人加专业技能44.30%、H3陌生人加专业技能43.29%、H5团伙6.21%、H2熟人无技能3.91%、H4陌生人无技能2.29%，后验合计1.0；前两名只差0.0101，结论为无法判断。稳健结论只有一条：具备专业技能合计87.59%，无技能合计6.20%。定性打分：H1净1.4、H3净0.4、H5净0.2、H2净0.0、H4净-1.0。独立审查0个blocker，通过。

新发现的矛盾（本轮核验5个指定入口时确认）：年龄表述19岁与“年方20岁”并存，实为周岁与虚岁口径差异；家属姐姐姓名在澎湃2016年采访中为化名，与中新网2021年“刁爱华”无法确认是否为同一人，不得混用；2022年5月30日南京警方回应“暂未侦破”，网传落网说法未获证实。

## 第二个案件：CASE-CN-1988-001（回溯校验）

1988-2002甘肃白银连环杀人案。选它不是因为它是悬案，而是因为它已侦破：已知结果可以校验引擎。引擎只读2016年8月25日之前的公开事实（证据截止日），抓获、DNA-Y比对、审判等事后信息只存在于独立的`ground-truth.json`校验文件，不进入推理；测试强制检查证据文本不含凶手姓名、落网、DNA-Y。

案件包：8个来源（山东高院引中国法院网、国际在线、中新社、央视新闻、人民日报海外版、凤凰网、界面新闻、中文维基交叉核对），10条证据（A 4、B 4、C 1、H 1），6个事件，5个实体，5条矛盾，5个竞争性假设，6个缺口。

本轮跑出的结论：H1单人连环、长期活动于白银、尾随陌生年轻女性69.17%，H2单人连环、外来流窜26.56%，H3多人或模仿2.09%，H4熟人针对1.93%，H5多起独立案件0.25%，前两名差距0.4261，结论为H1领先。校验5项全过：单人合计95.73%对多人/独立2.34%，H1高于H2，陌生人尾随合计95.73%对熟人针对1.93%，H1排名第一，独立案件假设垫底。定性打分一致：H1净2.2、H2净1.0、H3净0.0、H4净0.0、H5净-1.0。独立审查0个blocker，通过。

白银案新发现的矛盾（5条）：部督年份2001年8月与2004年8月说法不一；重启侦查年份2015年3月与2016年3月说法不一；白银与包头分布9加2与10加1说法不一（总数11起一致）；作案时段白天与夜间说法不一；首案月份1988年5月与6月说法不一。均已并存记录，未强行取舍。校验脚本：`python3 scripts/validate_baiyin.py`。

## 资料覆盖（模块9实测数）

- 南大案CASE-CN-1996-001：覆盖率65.9%（10项已覆盖/9项单来源/3项缺失，共22项）。缺失：C03案发时间窗口、C10物证清单与保存现状、C11 DNA/指纹比对现状。
- 白银案CASE-CN-1988-001：覆盖率52.4%（7项已覆盖/8项单来源/6项缺失，共21项，C16抛尸方式不适用已排除）。缺失：C05发现过程、C07身份确认过程、C17动机指向、C18诉讼进展、C20家属说法、C22同期原始报道（只有H级待核实材料，不计入覆盖）。

## 自动调查模式V1（2026-11-11，端到端测试中）

用户在前端输入一个调查方向（案件名或一句话）即开始自动跑。链路：`public/investigate.html`表单（方向、语言、地区、提示）→POST `/api/investigate`（`functions/api/investigate.js`，校验后写KV，键`job:<uuid>`，状态queued）→定时跑手`detective-os-job-watch`每10分钟轮询→`scripts/job.py poll/get/update`→`scripts/run_job.py <job_id>`跑抽取、似然、映射、草稿包、引擎、报告→结果写回KV→前端每5秒GET `/api/jobs?id=`轮询展示。读接口`functions/api/jobs.js`只读、无写入口，公网改不了任务状态。任务文档字段：job_id、direction、language、region、hints、status（queued/collecting/extracting/reasoning/done/failed）、stage、stage_note、events、result、error、created_at、updated_at。前端：https://detective-os.pages.dev/investigate.html。

机械部分在代码里，判断部分留给跑手与引擎规则：`detective_os/pipeline.py`（`plan_queries`生成查询清单；`extract_candidates`走MiniMax抽事实，每条引文逐字核验；`propose_likelihoods`按5类假设模板拟合P(证据|假设)，分批每批10条；`map_categories`把证据对应到覆盖清单条目，分批每批15条；`build_draft_pack`用统一先验0.2、似然夹到[0.2,0.8]、证据全C级；`run_draft`跑引擎加覆盖率并在报告前加草稿横幅）；`detective_os/llm.py`（MiniMax-M3，见下文凭证一节）。断点续跑：`runs/<job_id>/`下`candidates.json`、`likelihoods.json`、`categories.json`三份检查点，以`collected.json`的mtime校验（重新收集即失效）；重跑`run_job.py`会自动续跑，任务若在failed态先用`job.py update`复位到collecting。

### 凭证：位置与取用方式（值不在仓库里，绝不许写进来）

- **Kaggle**：CLI在`~/.local/bin/kaggle`（v2.2.5，不在默认PATH里，用前加`export PATH="$HOME/.local/bin:$PATH"`），认证文件`~/.kaggle/kaggle.json`（用户名nequexkaggle加api key）。key只存在于该文件与用户自己的Kaggle账号设置里，**本仓库没有任何key的值，绝不许把key写进README、issue、聊天记录或任何提交**——仓库是公开的，写进来等于把账号送人（额度每周30 GPU小时，会被刷光）。在虚拟机外工作时，由用户本人在自己的聊天里私下把key交给接手的AI，绝不走公开渠道。Notebook：`kaggle/detective-os-experiments.ipynb`，线上地址https://www.kaggle.com/code/nequexkaggle/detective-os-t4，实测2张Tesla T4（每张约14.56GB）。
- **MiniMax**：代码里没有明文key。Python侧用`/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`的`add_surrogate_to_request(request, "custom.minimax", allowed_hosts=["api.minimax.io","api.minimaxi.com","api.minimaxi.chat"])`在无Authorization头的urllib请求上挂代理凭证（`dynamic_credential_entry("custom.minimax", "api_key")`会报missing api_key surrogate，禁用）。调用：POST https://api.minimaxi.com/v1/text/chatcompletion_v2，模型MiniMax-M3，成功标志`base_resp.status_code===0`，正文在`choices[0].message.content`；M3是推理模型，max_tokens至少1024否则只思考不返回，抽取与似然用8192。书站Workers的同款写法在`~/workspace/sanguo/functions/api/chat.js`。
- **Cloudflare**：token经`dynamic_credential_entry("custom.cloudflare", "access_token")`取hsurr代理值当Bearer用，账号`3c76b79d615b6bc886fe564307682767`。该token只有Pages与KV权限，**D1与R2都没有**（`wrangler d1/r2`报Authentication error [code: 10000]），所以V1的任务库用KV不用D1：namespace `detective-os-jobs`，id `ae900386f76f465896f5e307baf12917`，绑定写进`wrangler.toml`（`[[kv_namespaces]] binding="JOBS"`）。D1的表结构在`scripts/schema.sql`，已写未建库；接D1须换有D1:Edit权限的token或在控制台建库。部署仍走`python3 deploy.py`（wrangler pages deploy，`functions/`随public/一起发）。

### 端到端踩过的坑（已修，写下来防重犯）

- MiniMax-M3偶发空回：单次调用可能思考半天返回空内容。已修：重试提到5次（间隔8秒）；似然与映射分批（10条/15条一批，70条单次调用必空）；单批失败跳过不致命（缺失的似然默认0.5、未映射的证据不链接覆盖率，如实报低不编造）。
- 抽取器不给category标签：LLM常返回空category，导致覆盖率0%（2026-11-11 09:17旧草稿即此bug）。已修：单独的`map_categories`调用做映射；`coverage.compute()`返回的键是`score`不是`score_pct`（`run_job.py`里换算）。
- 引文核验标点敏感：全角/半角引号与逗号导致合法引用被拒。已修：`verify_quote`归一化时去掉全部Unicode标点再比对子串，改写内容仍拒绝，短于4个骨架字符的引用拒绝。
- `job.py`的“无此任务”判断：任务文档自带`"error": null`键，failed任务的error是失败文案。已修：只认Function的404正文`"没有这个任务"`才算无任务；复位到collecting时清掉旧error。
- 沙箱出口缓存GET：同一URL重复GET会返回第一次的旧值，曾被误诊为KV跨区不一致与wrangler写不到namespace。已修：所有核验类GET加随机cache-buster（`job.py`的`api_get`已加）；KV读写走Cloudflare REST API直接调用（`job.py`的`kv_put`），不用`wrangler kv key`命令；Pages部署走wrangler仍正常。
- Cloudflare边缘403 urllib默认User-Agent：调自家Pages API须显式设浏览器式User-Agent（`job.py`已设`detective-os-runner/1.0`）。
- `run_job.py`的done更新与末尾打印：曾用`cov['score_pct']`在已写result.json后抛KeyError。已修：用局部变量`score_pct`。
- 虚拟机重启会杀死长任务（V1全程约12–15分钟，两次被重启打断）。已修：三份检查点加断点续跑；跑手正文仍要改成调`run_job.py`（见V0）。
- 覆盖路径归一化：收集步骤写自由文本路径（“browser.search news vertical: …”“browser.open …”）与状态ok/partial，`build_draft_pack`原样抄进coverage.json导致引擎步校验失败（E2E第8轮）。已修：`pipeline._normalize_paths`把路径归一到10个标准收集路径、状态归一到4个标准状态，原始文本保留在analyst_note里；测试覆盖归一化与草稿包校验。
- `bayesian()`的舍入是定死的：对数后验先舍入到4位小数再softmax，后验再舍入到4位小数；复算必须原样复制，阈值1e-9（T1运行3的教训）。

## 验收测试

`tests/test_acceptance.py`，11项（含1项护栏测试），全部通过；`tests/test_baiyin_validation.py`，6项，全部通过；`tests/test_coverage.py`，14项，全部通过；`tests/test_pipeline.py`，19项，全部通过（含抽取逐字核验、似然分批、映射分批、失败批次跳过、检查点存取与mtime失效、覆盖路径归一化、草稿包端到端）。合计50项全过：

1. 同一新闻10个转载版本只算1个独立来源
2. 两篇报道时间说法不同，两种说法都保留
3. 无可靠出处的传言不得列为事实，AI推断不得升级
4. 无证据的结论被标出
5. 新证据推翻旧假设时旧结论保留历史版本
6. 多假设都合理解时拒绝过早选定
7. 每个事实结论可追溯到原始资料
8. 区分“媒体报道警方说法”与“警方直接发布”
9. 明确说明公开资料无法回答的问题
10. 反方Agent真正提出反证
11. 护栏：提及不等于嫌疑人，传言依据不得标记嫌疑人
12. 覆盖清单：转载链归一后计数，传言与待核实不计入覆盖，缺失项与单来源项如实列出（南大案65.9%、白银案52.4%）

## 未完成事项

- V0收尾余项：删KV探针键`probe-direct`、定时任务`detective-os-job-watch`正文改成调`scripts/run_job.py`
- 前端工作站（React加TypeScript，10个导航页）未做
- Workers API、D1正式库、R2附件库未接（本地SQLite先行，结构已按D1兼容子集设计；Cloudflare token目前无D1/R2权限；V1任务库先用KV顶着）
- Provider Adapter（MiniMax、OpenAI兼容接口、本地模型）未做；本版推理为纯结构化计算，LLM只在自动调查管线里做抽取、似然拟合与覆盖映射
- Kaggle Notebook T1已完成（2026-11-10，版本4全部通过；报告在`kaggle/run1-output/`至`kaggle/run4-output/`；额度合计约0.23 GPU小时）
- GitHub仓库：https://github.com/nequex-eng/DETECTIVE-OS（公开，main分支，已推送）
- 1996年协查通报与认尸启示原始版面、1996年2月至4月排查同期报道原文尚未收入（已记为缺口G7、G8）

## 网站

Cloudflare Pages静态站（报告数据驱动，双案件版）：https://detective-os.pages.dev

部署：`python3 deploy.py`（wrangler direct upload，public/目录）。

## 下一步

见上文「接手任务书」V0、T2-T6，按顺序做。
