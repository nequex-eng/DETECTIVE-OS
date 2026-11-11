# 四、GitHub Actions部署凭证与Secrets配置

## 4.1 结论先说

**本次没有可用的GitHub Actions部署凭证可以代配，仓库里也没有现成的GitHub Actions。** 以下三点都是实测结论，不是推测：

1. 仓库里没有`.github/workflows/`目录，没有任何workflow文件，GitHub上从未配过Actions部署。
2. 本机`gh` CLI未登录（`gh auth status`：“You are not logged into any GitHub hosts”），没有可用的GitHub用户凭证来写Secrets。
3. Muse的GitHub App（nequex-eng）没有写Secrets的路径：它连创建仓库都返回403（2026-11-10实测）；它暴露的工具只有读操作与快照式推文件（`push-files`），没有创建Secret、配置Actions的接口。`github --help`列出的全部子命令是：status、install-url、authorize-url、exchange-code、disconnect、accounts、list-tools、call-read-tool、call-tool、push-files。
4. 最关键的一点：**Cloudflare API Token的原始值不在Muse侧，取不出来。** Muse安全连接里存的是真实Token，但代码只能拿到运行时一次性代用值（`hsurr:` surrogate，见03）。把surrogate写进GitHub Secrets既无效（短时有效、离境即换）也不安全。没有任何办法从Muse侧“导出”一个能长期使用的Token。

所以：Token必须新建，Secrets必须由用户（或持有GitHub与Cloudflare账号权限的人）在网页端完成。下面给出最小权限规格与一步步的操作。

## 4.2 新建Cloudflare API Token（最小权限）

在Cloudflare控制台（dash.cloudflare.com）→ My Profile → API Tokens → Create Token → Create Custom Token：

- Token name：`detective-os-deploy`（任意可辨认的名字）
- Permissions（只给这两组，不要给Account全权）：
  - `Account | Cloudflare Pages | Edit`（部署Pages项目detective-os用）
  - `Account | Workers KV Storage | Edit`（跑手写KV任务用；如只部署不跑任务，可暂不给）
- Account Resources：选定具体账户（id `3c76b79d615b6bc886fe564307682767`），不要选All accounts。
- Zone Resources：不填（本项目不用Zone资源）。
- 明确**不要**给的权限：D1（本项目暂不用；等T4要上D1时再另建一个带`Account | D1 | Edit`的Token）、R2、Account Settings、User。
- TTL：建议不设过期，或设90天并登记轮换日。Token只显示一次，创建后立即复制进下一步。

权限与现有Token的对照：现有Token只有Pages与KV（D1/R2调用返回10000鉴权错误）。新Token按上表建，与现有Token权限相同，另加说明：如ChatGPT要执行`scripts/schema.sql`（D1建表），需另行给D1权限或让用户在控制台建库——不要把D1权限塞进部署Token。

## 4.3 配置GitHub仓库Secrets

在GitHub仓库页 → Settings → Secrets and variables → Actions → New repository secret，建两个：

| Secret名 | 值 | 说明 |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | 4.2新建的Token值 | 只在这里填一次，永不写进代码、日志、聊天记录 |
| `CLOUDFLARE_ACCOUNT_ID` | `3c76b79d615b6bc886fe564307682767` | 账户标识符，不是密钥；也可直接写进workflow文件 |

或用已登录的`gh` CLI：

```bash
gh secret set CLOUDFLARE_API_TOKEN --repo nequex-eng/DETECTIVE-OS
gh secret set CLOUDFLARE_ACCOUNT_ID --repo nequex-eng/DETECTIVE-OS --body 3c76b79d615b6bc886fe564307682767
```

（第一条会交互式提示粘贴Token，不会在shell历史里留痕。）

## 4.4 GitHub Actions workflow（建议稿，未部署，需ChatGPT评审后提交）

以下workflow是建议稿，不是已部署的文件。把它存为`.github/workflows/deploy-pages.yml`前，请按仓库现状评审：部署命令与`deploy.py`一致，只是把Muse的surrogate换成GitHub Secrets里的真实Token。

```yaml
name: Deploy DETECTIVE OS to Cloudflare Pages
on:
  push:
    branches: [main]
    paths:
      - 'public/**'
      - 'functions/**'
      - 'wrangler.toml'
      - 'scripts/build_site.py'
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Build static site
        run: python3 scripts/build_site.py
      - name: Deploy to Cloudflare Pages
        run: npx -y wrangler@4 pages deploy public --project-name=detective-os --commit-dirty=true
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

注意：

- `paths`过滤避免改引擎代码也触发部署；`workflow_dispatch`允许手动触发。
- 构建步`build_site.py`读`reports/*-report.json`：这些报告文件已提交进仓库，所以Actions里能直接读；如果将来报告改为CI内生成，需要先在workflow里跑引擎（`python3 -m detective_os.cli run cases/...`）。
- wrangler版本固定`wrangler@4`，与`deploy.py`一致。
- 不要在workflow里回显Token，不要开`ACTIONS_STEP_DEBUG`。
- 本workflow只覆盖部署，不覆盖跑手（跑手需要Muse agent，见05）。

## 4.5 如何核验Secrets配好了（不泄露值）

- GitHub仓库页 → Settings → Secrets and variables → Actions，应看到两个Secret名（值不可见是正常的）。
- 手动跑一次workflow（Actions → Deploy → Run workflow），看部署步退出码为0，再打开https://detective-os.pages.dev/核验。
- 失败先看Actions日志的命令回显（Token本身不会被打印）；401/403先核对Token权限表（4.2）与账户id，再考虑重建Token。
