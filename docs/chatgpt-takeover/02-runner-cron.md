# 二、后台自动调查跑手

## 2.1 定时任务（完整定义）

完整正文与调度元数据见`files/cron-body.txt`（全文照录）。摘要如下：

- 任务id：`detective-os-job-watch`；标题：DETECTIVE OS自动调查跑手；状态：enabled。
- 触发频率：每10分钟一次（interval `10m`）；时区：Asia/Shanghai；超时：1800秒（30分钟）；自动重试：无（max_retries 0，on_failure false）。
- 首次触发：2026-11-11T09:01:44；交付：侦探推理破案引擎专属侧聊（chat_id 9f1d7651-1a8b-4c29-a8fc-fa7c495acd6f）。
- 执行类型：agent——每次触发由Muse运行环境唤醒一个agent，按正文执行；不是系统服务、不是常驻进程、不是Cloudflare Cron Trigger。
- 注意：正文第6、7步是`run_job.py`出现之前的旧版分步描述，当前实际执行路径是“收集→写collected.json→调`scripts/run_job.py <job_id>`”。把正文改成调run_job.py是README登记的收尾余项，改前以`files/cron-body.txt`为准。

## 2.2 完整流程（从委托到报告）

```
用户在investigate.html输入方向
  → POST /api/investigate（Functions，见files/functions/api/investigate.js）
  → KV写入 job:<uuid>，status=queued
  → 定时任务每10分钟唤醒agent跑手
  → scripts/job.py poll（只作线索）→ 对每条queued任务 job.py get 核实
  → 只接status确为queued的任务，一次一个
  → job.py update → collecting
  → 收集：plan_queries生成查询 → browser.search（新闻类加news vertical）+ browser.open
  → 写 runs/<job_id>/collected.json
  → scripts/run_job.py <job_id>（机械化执行，见2.4）
  → job.py update → done（带result.json）或 failed（带error）
  → agent在本对话汇报结果或失败原因
```

### 收集步（agent执行，Muse专有）

- 查询生成：`detective_os.pipeline.plan_queries(方向, 语言, 地区)`——基础查询加每个覆盖清单角度一条，方向语言与英文各一份，去重。
- 搜索与打开：browser.search（新闻类加news vertical）与browser.open逐个查。优先新华社、人民日报、澎湃、中新社、警方公开信息、法院文书等权威来源；非中文案件优先本地语言报道。
- 来源要求：至少3个独立来源；转载只算一个来源（同一消息20家转载=1个来源）。
- 产物：`runs/<job_id>/collected.json`，结构：
  ```json
  {
    "direction": "调查方向原文",
    "sources": [{"source_id": "S01", "title": "", "publisher": "",
                 "published_at": "", "url": "", "source_type": "news",
                 "is_reprint": false, "reprint_of": "", "notes": ""}],
    "texts": {"S01": "来源全文"},
    "paths_tried": [{"path": "web_search", "status": "found"}]
  }
  ```
  `paths_tried`在收集时常写自由文本（如`browser.search news vertical: …`、`browser.open <url>`，状态`ok`/`partial`）；`build_draft_pack`内的`_normalize_paths`会把它归一到10个标准收集路径与4个标准状态，原始文本保留在coverage项的analyst_note里（E2E第8轮的教训：原样抄进coverage.json会让引擎步校验失败）。
- 收集失败不致命于单个来源，但0个来源或0条核验事实会让任务失败。

### 任务文档结构（KV内，`job:<uuid>`）

```json
{
  "job_id": "uuid", "direction": "", "language": "zh", "region": "", "hints": "",
  "status": "queued|collecting|extracting|reasoning|done|failed",
  "stage": "同status", "stage_note": "",
  "events": [{"t": "ISO时间", "stage": "", "message": ""}],
  "result": null,
  "error": null,
  "created_at": "", "updated_at": ""
}
```

`result`（done时）结构见`files/scripts/run_job.py`末尾的result字典：case_id、case_name、verdict、posteriors（hypothesis_id/posterior/prior）、coverage（score_pct/covered/single/missing/total）、review_blockers、report_md（全文）。

## 2.3 相关脚本、配置文件、依赖包、目录结构

```
detective-os/
├── deploy.py                     # Pages部署（见01）
├── wrangler.toml                 # Pages项目 + KV绑定JOBS（见01）
├── .gitignore
├── functions/api/
│   ├── investigate.js            # POST /api/investigate：建任务，只写KV，不跑流程
│   └── jobs.js                   # GET /api/jobs：读单个任务或最近20个任务摘要
├── public/
│   ├── index.html                # build_site.py生成
│   ├── case-cn-1996-001.html     # build_site.py生成
│   ├── case-cn-1988-001.html     # build_site.py生成
│   └── investigate.html          # 手写intake页：表单 + 每5秒轮询GET /api/jobs?id=
├── detective_os/
│   ├── core.py                   # 来源注册（转载去重）、证据板（A–H分级）、时间线、实体图
│   ├── reasoning.py              # 矛盾引擎、假设引擎（贝叶斯）、调查规划、独立审查
│   ├── coverage.py               # 覆盖清单：10类22项，A–E级才计分，已覆盖须≥2独立来源
│   ├── pipeline.py               # plan_queries、extract_candidates、propose_likelihoods、
│   │                             # map_categories、build_draft_pack、write_draft_pack、run_draft
│   ├── llm.py                    # MiniMax-M3调用（只做抽取，见03）
│   ├── db.py                     # SQLite 14张表
│   ├── report.py                 # 带引用的Markdown报告
│   └── cli.py                    # run|check|coverage子命令
├── scripts/
│   ├── job.py                    # 跑手KV工具：poll/get/update（见2.5）
│   ├── run_job.py                # 单任务机械化执行（见2.4）
│   ├── cf.py                     # wrangler包装器（见01）
│   ├── build_site.py             # 静态站生成（见01）
│   ├── build_coverage.py         # 生成cases/*/coverage.json
│   ├── schema.sql                # D1建表（未执行，Token无D1权限）
│   ├── build_notebook.py         # 生成Kaggle Notebook
│   └── validate_baiyin.py        # 白银案回溯校验
├── cases/
│   ├── case-cn-1996-001/         # 南大正式案包（永不由跑手修改）
│   ├── case-cn-1988-001/         # 白银正式案包（永不由跑手修改）
│   └── draft-<job前8位>/          # 跑手生成的草稿包
├── runs/<job_id>/                # collected.json、检查点、result.json
├── reports/                      # 引擎报告（.md + .json）与detective-os.db
├── tests/                        # 50项测试（见06）
└── kaggle/                       # T1实验Notebook与运行报告
```

依赖：Python 3.12标准库（引擎与跑手脚本无第三方依赖）；Node/npx（仅用于拉取wrangler@4）；MiniMax调用走urllib（见03）。无requirements.txt、无package.json。

## 2.4 run_job.py（机械化执行，见files/scripts/run_job.py全文）

- 入口：`python3 scripts/run_job.py <job_id>`。前置条件：`runs/<job_id>/collected.json`已存在（由agent收集步写好）。
- 步骤：读collected.json→按live状态决定首更（已在extracting/reasoning则发“断点续跑”事件，不强制要求collecting；否则要求`--expect-status collecting`后置为extracting）→逐来源`extract_candidates`（MiniMax，逐字引用核验；单个来源失败只跳过并记录，0条候选才失败）→`build_draft_pack`（5个标准假设模板，先验均匀0.2，似然夹到[0.2,0.8]，证据全C级）→`propose_likelihoods`（分批，每批10个证据）→`map_categories`（分批，每批15个）→重建草稿包→`write_draft_pack`写`cases/draft-<前8位>/`→`run_draft`跑引擎加覆盖率→写`runs/<job_id>/result.json`→`job.py update --status done --expect-status reasoning --result <result.json>`。
- 检查点（断点续跑）：`runs/<job_id>/candidates.json`、`likelihoods.json`、`categories.json`，每个都盖collected.json的mtime戳；重收集（mtime变了）使全部检查点失效；重跑时已完成的阶段直接复用。两次虚拟机重启实测未丢进度。
- 异常：任何一步抛错都走except分支：`job.py update --status failed --error <原因前500字>`，进程退出码1。
- 红线（代码内）：永不碰两个正式案包；证据最高C级；似然默认0.5；草稿包带未审横幅。

## 2.5 环境变量、KV访问方式、任务认证机制

- 环境变量（跑手脚本实际用的）：
  - `CLOUDFLARE_API_TOKEN`：只在子进程环境里出现，由`deploy.py`/`scripts/cf.py`从Muse安全连接取代用值后注入；`scripts/job.py`的kv_put同样在函数内取取代用值，不读磁盘、不读`.env`。仓库里没有`.env`文件，跑手不依赖任何预设环境变量。
  - `CLOUDFLARE_ACCOUNT_ID`：固定值`3c76b79d615b6bc886fe564307682767`，写死在`deploy.py`与`scripts/cf.py`里（标识符，不是密钥）。
  - `JARVIS_AUTHD_SOCK`：Muse运行环境内部变量，默认`/run/hatch/auth/authd.sock`，只在Muse沙箱内存在（见03）。GitHub Actions/Cloudflare Workers里没有这个变量。
  - MiniMax调用不经过环境变量，见03。
- KV访问方式：
  - 读：优先走Function API `GET https://detective-os.pages.dev/api/jobs?id=<job_id>`（`scripts/job.py`的api_get，带随机`cb=`防缓存、5次重试、User-Agent `detective-os-runner/1.0`）。列表读`GET /api/jobs`只作线索。
  - 写：一律走Cloudflare REST API直接PUT（`scripts/job.py`的kv_put）：`PUT https://api.cloudflare.com/client/v4/accounts/3c76b79d615b6bc886fe564307682767/storage/kv/namespaces/ae900386f76f465896f5e307baf12917/values/job:<job_id>`，Bearer为运行时取的代用值。**不要用`wrangler kv key put`**（在本沙箱写不到Function看到的namespace，见01.7）。
  - Function侧读写走Pages绑定`env.JOBS`（`JOBS.put`/`JOBS.get`/`JOBS.list`）。
- 任务认证机制：
  - 对外：创建任务不需要登录（POST /api/investigate无鉴权，靠方向长度≤500字、语言与地区字段格式校验）；读任务不需要登录（GET /api/jobs公开）。**故意没有写入口**：只有跑手能改任务状态，公开互联网改不了进度与结果（`functions/api/jobs.js`头注释有说明）。
  - 对内：跑手写KV靠Cloudflare API Token（Bearer）；跑手读任务靠公开GET（无密钥）。任务id是随机UUID，不可猜；没有其他鉴权层。这是V1的取舍：防篡改靠“无写入口”，不靠鉴权；如需收紧，应在Function层加鉴权后再开放写入口（T4工作）。

## 2.6 失败重试、超时控制、日志记录、重复任务防护、状态回写

- 失败重试：
  - 定时任务级：无自动重试（retry max_retries 0）。一次触发失败不重跑；下一轮10分钟后只接仍为queued的任务。
  - MiniMax调用级：`call_minimax_retry`默认5次重试、每次间隔8秒、max_tokens 8192；单批失败（似然每批10个、映射每批15个）跳过该批、不致命。
  - 抽取级：单个来源抽取抛错只跳过该来源；0条候选事实才整任务失败。
  - 任务级：失败的任务可由人工（或GPT）复位：`job.py update <job_id> --status collecting …`后重跑`run_job.py`，检查点续跑。
- 超时控制：
  - 定时任务超时1800秒；单轮实际耗时约20分钟（E2E第8轮约1202秒，复跑约87秒因检查点复用）。MiniMax单次调用超时120秒；`job.py`的urlopen超时30秒；`api_get`重试间隔5秒、最多5次；`--expect-status`等待上限30秒。
  - 注意：抽取加映射阶段可能超过单轮1800秒预算时，任务会留在extracting状态；下一轮因“只跑queued”不会重复接手，需人工或后续轮次按检查点续跑（`run_job.py`的断点续跑分支就是为此设计的）。
- 日志记录：
  - 没有集中日志服务。日志分三处：①KV任务文档的`events`数组（每个阶段一条，带UTC时间戳）；②跑手进程的标准输出（收集、抽取、拟合的逐行打印）；③本对话的汇报（成功或失败都汇报，失败不得静默）。
  - 定时任务的运行记录在Muse的cron运行历史里（`cron.runs`），不在仓库里。
- 重复任务防护：
  - 只接queued：`job.py get`核实status确为queued才开工；collecting/reasoning中的任务视为另一轮正在跑，不得重复接手。
  - 一次只跑一个任务（正文第4步）。
  - `--expect-status`读后写保护：更新前等读到的状态符合预期才写，防止跨区KV读延迟导致旧状态覆盖新状态；30秒内等不到预期状态则拒绝写入并返回1。
  - `job.py update`的“任务不存在”判定只认Function的确切404正文`{"error":"没有这个任务"}`，失败任务的error字段不会被误认成“无此任务”。
- 状态回写机制：
  - 每次状态变化都是一次KV全文档PUT（读→改→写回整条job JSON），字段：status、stage、stage_note、events追加、error、result、updated_at。非failed更新会清掉旧error。
  - 状态机：queued → collecting → extracting → reasoning → done；任何一步失败→failed。failed可复位回collecting重跑。
  - 前端每5秒轮询GET /api/jobs?id=展示状态、阶段、事件与结果；结果含完整report_md，前端直接渲染。
