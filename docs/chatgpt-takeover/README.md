# DETECTIVE OS —— ChatGPT接管交接包

- 交接日期：2026-11-11
- 仓库：https://github.com/nequex-eng/DETECTIVE-OS（公开，main分支）
- 线上站：https://detective-os.pages.dev/
- 交接范围：只交付资料与必要的凭证配置说明。**不执行部署、不运行真实案件、不更改现有生产任务、不碰生产KV。**
- 本包不含任何密钥、Token、密码明文。凡是凭证，只写位置与取用方式，不写值。

## 文件清单

| 文件 | 内容 |
|---|---|
| `README.md`（本文件） | 总览、迁移矩阵摘要、权限缺口摘要、模拟验收入口 |
| `01-production-deployment.md` | 生产部署：部署流程、绑定关系、权限范围、部署脚本说明 |
| `02-runner-cron.md` | 后台自动调查跑手：定时任务、完整流程、脚本、环境变量、KV访问、认证、重试/超时/日志/防重、状态回写 |
| `03-dynamic-credentials.md` | dynamic_credentials调用方式、依赖模块、凭证获取流程、在Muse运行环境中的实际工作机制 |
| `04-github-actions-and-secrets.md` | GitHub Actions现状、Secrets配置（为什么本次无法从Muse侧代配）、最小权限Token规格、操作步骤 |
| `05-migration-matrix.md` | 哪些功能依赖Muse专有环境，哪些可以迁移到GitHub Actions或Cloudflare Workers |
| `06-simulation-acceptance.md` | 不启动新案件、不修改生产KV、不触发定时任务的前提下，如何做模拟验收 |
| `files/` | 逐字复制的关键文件（部署脚本、Functions、跑手脚本、引擎LLM/管线模块、wrangler.toml、cron正文、dynamic_credentials.py、.gitignore） |

`files/`内文件与仓库同路径文件内容一致（复制于2026-11-11 11:35），以仓库为准，`files/`只作交接快照。以下凡说“见files/…”即指本包内副本；仓库内原路径相同。

## 项目现状（接管时）

- 引擎：Python标准库，8模块加覆盖清单模块9，SQLite 14张表，CLI。三个案包：南大CASE-CN-1996-001（未侦破，28条证据，无法判断）、白银CASE-CN-1988-001（已侦破回溯校验，只读2016-08-25前事实，H1 69.17%领先，校验5项全过）、Isdal CASE-NO-1970-001（身份未明/死亡性质未决的可疑死亡，6个来源、16条证据、4个竞争假设，贝叶斯前两名差0.0306，输出undecided）。
- 自动调查模式V1已建成并跑通端到端：前端输入方向→Pages Functions写KV任务→定时跑手每10分钟轮询→`scripts/run_job.py`跑抽取、似然、映射、草稿包、引擎、报告→结果写回KV，前端轮询展示。端到端测试任务c23978f6（1988-2002白银连环杀人案重推）已完成：9个来源、63条事实全C级、H3陌生人加技能领先52.45%、覆盖率31.8%、审查6个blocker。测试65项全过。
- 接手任务书在仓库README.md「接手任务书」一节：V0、V1、T2已完成；T3 React+TypeScript十模块工作站已完成代码与CI构建验收，生产Pages部署待标准Cloudflare凭证/上传通道。下一步是T4 Workers API加D1加R2、T5 Provider Adapter、T6补1996年原始来源缺口。另两件收尾余项：删KV探针键`probe-direct`、定时任务正文改成调`scripts/run_job.py`。T2报告和静态页已由CI生成artifact，65项测试全过。
- 红线（代码与流程都已强制，接管后同样适用）：抽取证据最高C级，A/B级永远要人工确认；不得根据网络传言指认现实中的活人为凶手；自动产出的报告带“草稿（未审）”横幅；不得修改两个正式案包及它们的报告；引用必须逐字出自来源原文；不得编造事实。

## T3前端工作站验收结果（2026-11-11）

- 新增React+TypeScript十模块工作站：案件中心、来源库、证据板、时间线、关系图谱、矛盾实验室、假设实验室、调查计划、审查室、最终报告。
- 工作站数据由三个案包与引擎报告构建，不使用假数据；来源和证据编号可回链；F/G/H级无来源记录明确标示。
- `scripts/build_site.py`对三个案包只读运行引擎，生成静态JSON、Markdown报告与案件页；`deploy.py`先构建前端和数据再调用Wrangler。
- TypeScript检查、Vite构建、静态数据构建和68项测试全部通过。artifact：https://github.com/nequex-eng/DETECTIVE-OS/actions/runs/42956572177。
- 生产Pages尚未部署；缺标准Cloudflare部署凭证/上传通道。没有声称线上已更新。

## T2第三案验收结果（2026-11-11）

- 案包：`cases/case-no-1970-001/`；6个独立来源、16条证据（C15/D1）、7个事件、10个实体、6条关系、4条解释分歧、8项缺口、22项覆盖清单（18项适用）。
- 贝叶斯：H2 28.35%、H1 25.29%、H3 25.27%、H4 21.09%；前两名差0.0306，正确输出`undecided`。定性H3净1.3领先，报告保留两种口径差异，不将其解释为犯罪概率。
- 覆盖率41.7%（3 covered/9 single/6 missing of 18 applicable）；调查计划11项；独立审查0 blocker。
- CI：68项测试通过；案包check、报告生成、静态站构建、artifact上传全部通过。运行记录：https://github.com/nequex-eng/DETECTIVE-OS/actions/runs/42955826149。
- 生产边界：没有触碰生产KV、没有启动自动调查任务、没有部署Pages。

## 迁移矩阵摘要（详见05）

- 可直接迁移：静态站构建（`scripts/build_site.py`）、引擎与测试（纯标准库Python）、Pages部署（wrangler pages deploy）、KV REST读写（`scripts/job.py`的kv_put只是REST调用）。
- 需替换才能迁移：跑手的收集步（现在靠Muse的browser.search/browser.open；迁出后需接搜索API或无头浏览器）、LLM调用认证（现在靠Muse代管的MiniMax凭证；迁出后需自备MiniMax API key）、定时触发（现在靠Muse的cron；迁出后用GitHub Actions schedule或Cloudflare Workers Cron Triggers）。
- 不能迁移：Muse agent本身（判断、去重决策、异常处理）、dynamic_credentials/authd代管凭证机制、Muse的cron调度器。

## 权限缺口摘要（详见04）

- 现有Cloudflare API Token（存在Muse的安全连接里，原始值取不出来）只有Pages与KV权限；D1、R2调用返回鉴权错误10000。`scripts/schema.sql`（D1 jobs表）已写好但从未执行。
- `.github/workflows/ci.yml`现已存在并可运行：检查V1 intake与React十模块、安装前端依赖、TypeScript类型检查、Vite构建、验证三个案包、生成引擎报告与静态数据、构建案件页、运行68项测试并上传完整workbench artifact。该CI不部署Pages，也不写生产KV。
- Cloudflare生产部署仍无可用的GitHub Actions部署凭证：当前项目仍为Direct Upload/ad_hoc部署，Muse的动态凭证不能作为GitHub Secret使用。04给出最小权限Token规格与创建、配置步骤，由用户或ChatGPT在Cloudflare控制台与GitHub网页端完成。

## 模拟验收入口（详见06）

只读验收三步：①本机跑50项测试；②用CLI在副本里重跑两个正式案包并核对后验；③用`wrangler pages dev`加本地KV在本地跑通 intake→创建任务→轮询的闭环。**禁止**向生产`https://detective-os.pages.dev/api/investigate` POST新方向、禁止对生产KV执行写操作、禁止手动触发或修改定时任务。
