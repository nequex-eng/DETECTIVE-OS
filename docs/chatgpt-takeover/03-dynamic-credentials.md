# 三、dynamic_credentials：调用方式、依赖模块、凭证获取流程、工作机制

## 3.1 这是什么

`dynamic_credentials`是Muse运行环境提供的凭证代管机制：真实密钥只存在Muse的安全连接存储里，代码永远拿不到明文。代码向本机authd服务要一个一次性代用值（surrogate，形如`hsurr:…`），把它放在请求的规定位置发出；Muse的出口网关（Sentinel/authd）在请求离境时把代用值换成真实凭证，只发往注册过的主机。代用值本身在Muse沙箱之外没有任何用处。

关键推论（接管时必须先理解）：**Muse之外的任何环境（GitHub Actions、Cloudflare Workers、ChatGPT自己的机器）都没有authd、没有surrogate、拿不到这些凭证。**迁出后必须用真实密钥重建认证（见05、04）。

## 3.2 依赖模块

- 唯一依赖文件：`/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`。本包已逐字复制一份在`files/dynamic_credentials.py`（Muse系统文件，不属于本仓库；复制仅供阅读机制）。
- 该文件只用Python标准库（socket、json、urllib、http.client）。
- 使用方在文件头加：`sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")`，然后`from dynamic_credentials import dynamic_credential_entry`或`add_surrogate_to_request`。

## 3.3 两个调用方式（本项目实际用的）

### 方式A：取一个条目，自己放进请求（Cloudflare用）

```python
from dynamic_credentials import dynamic_credential_entry
entry = dynamic_credential_entry("custom.cloudflare", "access_token")
surrogate = str(entry.get("surrogate", "")).strip()
# 校验：必须以 hsurr: 开头，否则视为不可用
```

- `dynamic_credential_entry(credential_name, entry_name="access_token")`：向authd要指定连接、指定条目的代用值，返回字典（含`surrogate`与`placement`）。
- 本项目用法：
  - `deploy.py`与`scripts/cf.py`：取到surrogate后放进子进程环境变量`CLOUDFLARE_API_TOKEN`，再调`npx wrangler`。wrangler把它当普通Bearer Token用；出口网关在请求发往api.cloudflare.com时换成真实Token。
  - `scripts/job.py`的kv_put：取到surrogate后放进`Authorization: Bearer <surrogate>`头，直接调Cloudflare REST API。
- 校验规则：凡取到的值必须以`hsurr:`开头，否则当作不可用并报错退出；绝不打印、绝不写盘、绝不写日志。

### 方式B：把代用值附加到urllib请求上（MiniMax用）

```python
from dynamic_credentials import add_surrogate_to_request
add_surrogate_to_request(req, "custom.minimax",
                         allowed_hosts=["api.minimax.io",
                                        "api.minimaxi.com",
                                        "api.minimaxi.chat"])
```

- `add_surrogate_to_request(request, credential_name, entry_name="access_token", allowed_hosts=[...])`：先校验请求URL的主机在允许列表里，再取条目，按该条目登记的`placement`放进请求（本项目两个连接都是`bearer_header`，即`Authorization: Bearer <surrogate>`）。
- 本项目用法：`detective_os/llm.py`的`call_minimax`。见`files/detective_os/llm.py`全文。
- 安全规则：请求禁用重定向（llm.py自带NoRedirect：重定向直接抛错），防止已附凭证的请求被带到未注册主机。

## 3.4 各连接的条目名（实测，踩过坑）

| 连接 | 条目名 | 说明 |
|---|---|---|
| `custom.cloudflare` | `access_token` | `dynamic_credential_entry("custom.cloudflare", "access_token")`可用，返回hsurr代用值 |
| `custom.minimax` | `access_token` | `add_surrogate_to_request(req, "custom.minimax")`默认就取这个条目，可用 |
| `custom.minimax` | `api_key` | **不可用**：`dynamic_credential_entry("custom.minimax", "api_key")`报“missing api_key surrogate”。不要用这个条目名 |

连接注册信息（重建连接时用，值不在此）：

- custom.cloudflare：provider `cloudflare`，auth_scheme `api_key`，placement `bearer_header`，api_hosts `["api.cloudflare.com"]`。注意：仓库里`custom-connectors/custom.cloudflare/CONNECTOR.md`是未填完的模板（占位符未替换），不要以它为准；以本节与`deploy.py`的实际行为为准。
- custom.minimax：provider `minimax`，auth_scheme `api_key`，placement `bearer_header`，api_hosts `["api.minimax.io", "api.minimaxi.com", "api.minimaxi.chat"]`。实测：2026-11-03起`api.minimaxi.com`可用，`api.minimax.io`不接受该key。

## 3.5 凭证获取流程（运行时，逐步）

1. 代码调`dynamic_credential_entry`或`add_surrogate_to_request`。
2. helper用Unix socket连本机authd：默认socket路径由环境变量`JARVIS_AUTHD_SOCK`给，未设则为`/run/hatch/auth/authd.sock`；POST `/v1/credentials/surrogate`，body `{"name": "<连接名>"}`，超时5秒。
3. authd返回JSON，含该连接各条目的`surrogate`与`placement`；helper只取所要条目，校验`hsurr:`前缀。
4. 代码把surrogate放进请求的规定位置（Bearer头或环境变量）。
5. 请求出沙箱时，出口网关核对目标主机已注册，把surrogate换成真实凭证再转发；目标主机看到的是真实密钥，代码全程看不到。
6. 失败时：authd非200或无该条目→抛`DynamicCredentialError`；调用方按失败处理（部署脚本返回1；llm重试5次后抛错；run_job.py把任务标failed）。

## 3.6 MiniMax调用细节（llm.py，跑手抽取用）

- 接口：`POST https://api.minimaxi.com/v1/text/chatcompletion_v2`，模型`MiniMax-M3`，temperature 0.2。
- 成功判定：`base_resp.status_code === 0`，正文在`choices[0].message.content`。
- M3是推理模型：`max_tokens`必须≥1024，否则只思考不返回内容；抽取类调用用8192。空内容视为失败，重试5次、间隔8秒。
- 规则：只抽取调用方传入的来源文本里的事实；每个抽取项必须带逐字引用，pipeline会逐字核验；不算概率、不编造事实；抽取结果最高C级。
- 冒烟测试：`python3 -m detective_os.llm`（会真实调一次MiniMax，回答“今天是星期几”，max_tokens 1024）。

## 3.7 在Muse运行环境中的实际工作机制（给接管者的要点）

- authd只存在于Muse沙箱本机（Unix socket文件），不是网络服务；离开Muse VM就没有这个文件，helper会直接连不上。
- surrogate是一次性、短时有效的代用凭证；把它复制到别处、写进GitHub Secrets、或事后重放，都无效。
- 真实密钥的注册与轮换在Muse的安全连接界面完成，不在代码、不在仓库、不在任何文档里。本包不含任何密钥值，ChatGPT如需重建连接，找用户在Muse里重新走连接流程，或直接用真实密钥（见04）。
- 沙箱出网有代理：Python urllib默认User-Agent会被Cloudflare边缘403（job.py已显式设置UA）；沙箱出口会对`api.cloudflare.com`的GET做缓存（读状态要加cache-buster，见01.7）。
