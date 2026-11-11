# 六、模拟验收：不启动新案件、不修改生产KV、不触发定时任务

以下验收全部在**副本**里做，零生产写操作。开始前先确认三条禁令：

- 禁止向生产`https://detective-os.pages.dev/api/investigate` POST任何新方向（那会创建真实任务并唤醒跑手）。
- 禁止对生产KV执行任何写操作（不调`job.py update`、不调REST PUT、不删`probe-direct`以外的任何键；`probe-direct`本身也是收尾余项，验收期间同样不动）。
- 禁止手动触发、修改、停用定时任务`detective-os-job-watch`（不调`cron.run`、`cron.update`、`cron.stop`）。

## 6.1 准备：建一个隔离副本

```bash
cp -r ~/workspace/detective-os /tmp/detective-os-sim
cd /tmp/detective-os-sim
# 副本里不含任何凭证；deploy.py与job.py在副本里会因取不到surrogate而失败，这是预期的
```

所有后续命令都在`/tmp/detective-os-sim`里跑，不动原仓库。

## 6.2 验收一：单元测试（无网络、无KV）

```bash
python3 -m unittest discover -s tests
```

- 预期：`Ran 50 tests`，`OK`。覆盖：验收测试11项、白银校验6项、覆盖清单14项、管线19项（含抽取逐字核验、似然分批、映射分批、失败批次跳过、检查点存取与mtime失效、覆盖路径归一化、草稿包端到端）。
- 失败先看具体用例名，不要改生产代码；只改副本排查。

## 6.3 验收二：引擎只读重跑两个正式案包

```bash
python3 -m detective_os.cli run cases/case-cn-1996-001
python3 -m detective_os.cli run cases/case-cn-1988-001
python3 -m detective_os.cli check cases/case-cn-1996-001
python3 -m detective_os.cli coverage cases/case-cn-1996-001
```

- 预期：南大案后验H1 44.30%、H3 43.29%，结论undecided（前两名差0.0101）；白银案H1 69.17%第一、差0.4261 leading；覆盖率南大65.9%、白银52.4%。与仓库`reports/*-report.json`里的数逐项核对，差值应为0.0（引擎的`bayesian()`在softmax前把对数后验舍入到4位小数，复算必须原样复制，阈值1e-9）。
- 注意：`run`会在副本的`reports/`里重写报告与`detective-os.db`，原仓库不受影响。`check`与`coverage`是只读的。

## 6.4 验收三：静态站生成

```bash
python3 scripts/build_site.py
```

- 预期：生成`public/index.html`与两个案件页，打印`built index.html (2 cases)`。用浏览器打开副本的`public/index.html`本地文件核对数字与报告一致。

## 6.5 验收四：Functions闭环（本地KV，不碰生产）

```bash
npx -y wrangler@4 pages dev public --kv JOBS=<本地命名空间id>
```

- `--kv`会在本地起一个miniflare KV，任务只写本地，不碰生产namespace。
- 在本地地址上：POST一个测试方向到`/api/investigate`，应返回201与job_id；GET `/api/jobs?id=<job_id>`，应返回queued任务；GET `/api/jobs`，应列出该任务。
- 验收完关掉dev服务，本地KV随进程销毁，不留痕迹。

## 6.6 验收五：run_job.py全链路（本地，带隔离改造）

`run_job.py`默认通过`scripts/job.py`读写**生产**API，因此验收前必须在**副本**里做一处隔离改造，再跑：

1. 在副本里把`scripts/job.py`顶部的`API = "https://detective-os.pages.dev/api/jobs"`改成验收四里`wrangler pages dev`的本地地址（如`http://localhost:8788/api/jobs`）。
2. 把`scripts/job.py`的kv_put改成调本地dev服务背后的miniflare KV，或更简单：让本地dev服务先跑起来，再用副本的`job.py`读写它（kv_put的目标URL也要改成本地Cloudflare API模拟——miniflare不提供REST端点，所以更实际的做法是：把kv_put临时改成读写本地一个JSON文件做KV替身，跑完即删）。
3. 复制一份已有的`runs/c23978f6-56f1-4789-b488-b36c4b9117a7/collected.json`到副本`runs/<新测试job_id>/collected.json`（只用它的9个来源文本作输入，不产生新收集），再跑`python3 scripts/run_job.py <新测试job_id>`。
4. 预期：抽取、似然、映射、草稿包、引擎、报告、result.json全链路跑通，任务在本地KV里变为done；报告带草稿横幅、证据全C级。
5. 注意：这一步会真实调MiniMax（需自备key替换llm.py的凭证调用，或用测试里的stub caller思路跳过真实调用）；验收完删除副本，不把改造带回仓库。

如果第5步的隔离改造成本太高，可降级验收：只跑`detective_os.pipeline`的各函数（抽取用测试里的stub caller、似然与映射用小批量），加验收二、三、四，已能覆盖除“真实MiniMax全链路”外的全部环节；真实MiniMax全链路等接管后第一件真实任务再验证。

## 6.7 验收通过标准

- 6.2五十项全过；6.3两案后验与仓库报告差值0.0；6.4两案页生成；6.5本地创建与读取闭环通；6.6（如做）本地done且草稿横幅与全C级成立。
- 验收全程生产侧零变化：生产KV键不变、生产任务状态不变、定时任务未被触发、仓库main分支未被改动（除非本交接包本身的提交）。
- 验收中发现的任何问题，先记在交接包的问题清单里，不要直接改生产代码；改动走正常流程（改→测→提交→评审→部署）。
