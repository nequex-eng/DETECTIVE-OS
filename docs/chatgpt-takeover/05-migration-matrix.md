# 五、迁移矩阵：什么依赖Muse专有环境，什么可以迁移

## 5.1 可以直接迁移（换真实凭证即可，不改逻辑）

| 功能 | 现状 | 迁出方式 |
|---|---|---|
| Pages部署 | `deploy.py`调`npx wrangler pages deploy` | GitHub Actions workflow（见04.4），Secrets里放真实Token |
| 静态站生成 | `scripts/build_site.py`（纯标准库Python） | 同上，在Actions里先跑再部署 |
| 引擎与测试 | `detective_os/*`、`tests/*`（纯标准库Python，50项测试） | 任何Python 3.12环境；Actions里跑`python3 -m unittest discover -s tests` |
| KV REST读写 | `scripts/job.py`的kv_put（纯REST PUT）与api_get（公开GET） | 真实Token替换surrogate即可；注意cache-buster与User-Agent两处细节（见01.7） |
| Functions | `functions/api/*.js`（零依赖） | 已在Cloudflare上，与部署一起走；不依赖Muse |
| 报告生成 | `detective_os/cli.py run`、`run_draft` | 纯Python，任何环境可跑 |

## 5.2 需要替换部件才能迁移

| 功能 | 现在依赖什么 | 迁出后替换成什么 |
|---|---|---|
| 跑手收集步 | Muse的browser.search（news vertical）与browser.open | 搜索API（如Tavily、Bing Search、Serper）加HTTP抓取，或无头浏览器（Playwright）。注意：X/部分新闻站有登录墙与反爬，Muse的浏览器能过的墙，普通抓取未必能过；收集质量可能下降，需重新测 |
| LLM抽取 | Muse代管的MiniMax凭证（surrogate） | 自备MiniMax API key（`Authorization: Bearer <真实key>`调同一接口`POST https://api.minimaxi.com/v1/text/chatcompletion_v2`，模型MiniMax-M3，max_tokens 8192）。抽取提示词与逐字核验逻辑在`detective_os/pipeline.py`，不用改 |
| 定时触发 | Muse的cron（每10分钟唤醒agent） | 二选一：①GitHub Actions `schedule`（cron表达式，最小间隔5分钟）跑`run_job.py`；②Cloudflare Workers Cron Triggers调一个Worker入口再触发后续步骤。注意：Actions的schedule不是精确时钟，免费额度有分钟数上限 |
| 跑手编排 | Muse agent（读任务、判断、异常处理、汇报） | 需写成确定性编排：一个Python或JS的runner，按cron正文第1–9步顺序执行，失败写failed并报警（邮件/飞书/Slack任选）。agent的临场判断（来源取舍、失败重试决策）要写成规则，否则行为会变 |
| 凭证管理 | Muse安全连接（authd/surrogate） | 各平台自己的Secrets：GitHub Secrets（Actions）、Cloudflare Workers Secrets（Workers）、或密钥管理服务。真实密钥永不进仓库 |

## 5.3 不能迁移（Muse专有，迁出即失去）

- Muse agent本身：收集时的来源判断、转载去重决策、异常时的临场处理、失败后的人话汇报。迁出后这些要么写成规则、要么由人接手。
- dynamic_credentials/authd机制：见03。Muse之外没有authd，没有surrogate。
- Muse的cron调度器与它的运行记录、审批卡、对话交付：迁出后触发与汇报都要重建。
- browser.search/browser.open的实时搜索能力与登录态：Muse浏览器里沉淀的登录会话（如需）无法导出。

## 5.4 哪些权限目前无法由GitHub/Cloudflare API获得

- Muse侧的凭证原始值：Cloudflare Token、MiniMax key的真实值都只存在Muse安全连接里，API取不出来（只能拿到一次性surrogate）。新环境必须用新密钥，不能“继承”。
- Cloudflare D1/R2权限：现有Token没有（调D1/R2返回10000）。这不是API拿不到，而是现有Token没配；用户可在控制台给新Token加上（见04.2），或在控制台直接建D1库与R2桶。
- GitHub仓库Secrets的写权限：Muse的GitHub App没有（连建仓库都403）。必须由仓库管理员在网页端或已登录的`gh` CLI完成。
- Muse cron的调度权：Muse运行环境的内部功能，没有公开API；ChatGPT接管后如需保留定时跑手，要么留在Muse侧、要么按5.2迁到Actions/Workers Cron。
- Kaggle API key：只存在`~/.kaggle/kaggle.json`（本机文件）与用户Kaggle账户设置里，仓库README只写了位置，不含值。T1实验如需重跑，找用户私下提供，不要写进仓库、聊天记录或交接文档。
