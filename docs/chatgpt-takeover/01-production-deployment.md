# 一、生产部署资料

## 1.1 部署总览

- 部署目标：Cloudflare Pages项目`detective-os`，公开地址https://detective-os.pages.dev/
- 部署方式：Pages Direct Upload（`wrangler pages deploy`），不走GitHub自动部署；仓库只是源码存放处，部署由本机脚本触发。
- 部署入口脚本：`deploy.py`（仓库根目录）。见`files/deploy.py`全文。
- 静态站生成器：`scripts/build_site.py`。见`files/scripts/build_site.py`全文。
- wrangler通用包装器：`scripts/cf.py`。见`files/scripts/cf.py`全文。
- 配置：`wrangler.toml`。见`files/wrangler.toml`全文。

## 1.2 部署流程（逐步）

1. 生成静态站：`python3 scripts/build_site.py`
   - 读`reports/<CASE>-report.json`与案包（`cases/<dir>/case.json`、`sources.json`、`evidence.json`），生成`public/index.html`与`public/<case>.html`。
   - 只认引擎真实输出：没有报告的案子不生成页面，绝不编造数字。
   - 案子列表写死在`CASES = ["case-cn-1996-001", "case-cn-1988-001"]`；新案要先改这个列表再生成。
   - `public/investigate.html`是手写的静态intake页，不由build_site.py生成；构建器不清空`public/`，所以它不会被覆盖。
2. 部署：`python3 deploy.py`
   - 脚本从Muse安全连接取Cloudflare凭证代用值（见03），只通过子进程环境变量`CLOUDFLARE_API_TOKEN`与`CLOUDFLARE_ACCOUNT_ID`传给wrangler，不打印、不落盘。
   - 实际命令：`npx -y wrangler@4 pages deploy public --project-name=detective-os --commit-dirty=true`，工作目录为仓库根目录。
   - wrangler同时上传`public/`静态资源与`functions/`（Pages Functions bundle）。部署日志里出现“Uploading Functions bundle”即表示Functions已随站发布。
   - `wrangler.toml`里`pages_build_output_dir = "public"`；`compatibility_date = "2026-11-10"`。
3. 核验：打开https://detective-os.pages.dev/，确认案件列表；打开https://detective-os.pages.dev/investigate.html，确认intake页可加载。Functions是否生效可用只读GET验证：`curl "https://detective-os.pages.dev/api/jobs?cb=<随机数>"`应返回任务列表JSON（不含result正文）。

## 1.3 Pages Direct Upload的打包与上传方式

- 静态资源：`public/`目录整体上传（`index.html`、两个案件页、`investigate.html`）。无构建步骤（无npm build、无框架打包），build_site.py只做字符串拼接生成HTML。
- Functions：`functions/api/investigate.js`（POST /api/investigate，创建任务）与`functions/api/jobs.js`（GET /api/jobs，读任务与列表）。Pages Functions约定：文件路径即路由。部署时wrangler把`functions/`打成Worker bundle随Pages项目一起上传，不需要单独的Worker项目。
- 没有独立的Worker、没有`wrangler.toml`里的`[build]`，没有CI。每次部署都是`deploy.py`一次性全量上传。
- 漂亮URL：Pages会把`/investigate.html`重定向到`/investigate`（308），正常现象，页面可用。

## 1.4 绑定关系（实测）

| 资源 | 值 | 说明 |
|---|---|---|
| Cloudflare账户 | id `3c76b79d615b6bc886fe564307682767`（登录邮箱nequex@gmail.com） | 标识符，不是密钥，可公开在代码与文档里；已写进`deploy.py`与`scripts/cf.py` |
| Pages项目 | `detective-os` | https://detective-os.pages.dev/ |
| KV namespace | `detective-os-jobs`，id `ae900386f76f465896f5e307baf12917` | 绑定名`JOBS`，写在`wrangler.toml`的`[[kv_namespaces]]`段 |
| Functions绑定 | `env.JOBS` | 两个Function都先判`if (!env.JOBS) return 503`；部署后曾用Cloudflare API核验生产配置里kv_namespaces确为JOBS→ae900386 |

KV里当前键（2026-11-11核实）：`job:c23978f6-56f1-4789-b488-b36c4b9117a7`（端到端测试任务，已done，草稿）与`probe-direct`（探针残留，待删，见README收尾余项）。除此之外没有其他生产任务键。**交接期间不要删改任何键。**

## 1.5 权限范围（实测结论）

- 现有Token（Muse安全连接`custom.cloudflare`）能做：Pages部署、KV读写（REST与Functions绑定）。
- 现有Token不能做：D1与R2。`wrangler d1 list/create`与`wrangler r2 bucket list`均返回“Authentication error [code: 10000]”。因此V1用KV存任务，`scripts/schema.sql`（D1 jobs加job_events表）已写好但从未执行，D1是后续选项（Token拿到D1:Edit权限、或用户在控制台建库后才能用）。
- Token的完整权限清单在Muse侧不可读（只知道能用与不能用的两端）；新Token按04的最小权限规格重建，不复用旧Token。
- KV免费额度对单用户V1足够（每天1000次写）。

## 1.6 相关脚本清单

| 脚本 | 用途 | 凭证 |
|---|---|---|
| `deploy.py` | Pages部署 | Cloudflare surrogate（运行时取） |
| `scripts/cf.py` | wrangler通用包装（d1/pages/kv等子命令透传） | 同上 |
| `scripts/build_site.py` | 生成public/静态站 | 无 |
| `scripts/build_coverage.py` | 生成`cases/*/coverage.json` | 无 |
| `scripts/build_notebook.py` | 生成Kaggle Notebook | 无（Kaggle CLI另见README） |
| `scripts/validate_baiyin.py` | 白银案回溯校验 | 无 |
| `scripts/job.py` | 跑手KV读写工具 | Cloudflare surrogate（kv_put） |
| `scripts/run_job.py` | 单任务机械化执行 | MiniMax surrogate（经pipeline/llm）加Cloudflare surrogate（经job.py） |
| `scripts/schema.sql` | D1建表（未执行） | 执行时需D1权限的Token |

依赖：Python 3.12标准库（引擎、跑手脚本无第三方依赖）；Node/npx（仅用于拉取`wrangler@4`）；无`requirements.txt`、无`package.json`、无锁文件。Functions是零依赖原生JS（`functions/api/*.js`）。

## 1.7 已知坑（部署侧，实测）

- wrangler.toml是绑定的唯一可信来源：`wrangler pages deploy`会按toml重写项目绑定，后台单独PATCH的绑定部署一次就被清掉。改绑定必须改toml，部署完再GET项目核验。
- Pages子域名全球唯一：`detective-os.pages.dev`已是本项目，改名需先确认未被占。
- wrangler CLI的KV命令在本沙箱不可信：`wrangler kv key put/get/delete --binding JOBS`打印的namespace id是对的，但写入落不到REST API与Function看到的同一个namespace里（2026-11-11三组对照实测）。KV读写一律走REST API（`scripts/job.py`的kv_put就是这么做的）；Pages部署走wrangler没问题。
- 沙箱出口代理会缓存`api.cloudflare.com`的GET响应：不用cache-buster的REST GET可能返回旧状态。核验任务状态优先走Function API（GET /api/jobs?id=），或带随机`cb=`参数的REST GET。
- Cloudflare边缘会403 Python urllib的默认User-Agent：`scripts/job.py`的api_get显式发`User-Agent: detective-os-runner/1.0`。
