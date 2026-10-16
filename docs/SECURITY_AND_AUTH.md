# 安全与认证配置

工作流 API 使用 Bearer Token 认证。流程追踪页面本身可以打开，但读取任务和员工数据的 `GET /api/workforce` 需要管理员权限。

## 环境变量

请在启动服务的同一终端配置凭证。不要把真实 Token 写进仓库、截图、公开 issue 或 shell 历史。

### macOS / Linux

```bash
export JARVIS_ADMIN_TOKEN='替换成至少 32 位随机管理员令牌'
export JARVIS_WORKER_TOKENS='{"researcher":"替换成独立员工令牌","analyst":"替换成另一枚独立员工令牌"}'
export JARVIS_WORKER_CAPABILITIES='{"researcher":["research"],"analyst":["analysis"]}'
export JARVIS_WORKFORCE_STORE='./data/workforce.json'
python -m mvp.server
```

### PowerShell

```powershell
$env:JARVIS_ADMIN_TOKEN = '替换成至少 32 位随机管理员令牌'
$env:JARVIS_WORKER_TOKENS = '{"researcher":"替换成独立员工令牌","analyst":"替换成另一枚独立员工令牌"}'
$env:JARVIS_WORKER_CAPABILITIES = '{"researcher":["research"],"analyst":["analysis"]}'
$env:JARVIS_WORKFORCE_STORE = '.\data\workforce.json'
python -m mvp.server
```

以上 Token 仅为配置格式示例，不是可用凭证。管理员 Token 与每个员工 Token 必须不同。服务端未配置管理员 Token 时，管理 API 不应被视为已安全配置。

## Dashboard API 访问模式

- 默认模式要求管理员 Token；主工作台和试玩页可在顶部输入 Token，凭证只保留在当前页面内存中。
- 纯本地、无真实模型/搜索配置的模拟演示，可显式设置 `JARVIS_PUBLIC_DEMO=true`。此模式禁止同时配置任何 workforce token、搜索端点或模型凭证。
- 不要在公网服务上启用 `JARVIS_PUBLIC_DEMO=true`。部署环境应设置强随机 `JARVIS_ADMIN_TOKEN`，并将 `JARVIS_PUBLIC_DEMO=false`。
- 未配置管理员 Token 时，受保护 API 会 fail closed；健康状态接口仍可用于服务存活探测。

## 角色边界

- **admin**：读取监控快照、创建/合并/取消/重试任务、记录验证结果等管理操作。
- **worker**：只能用自己的 Token 领取符合能力范围的任务、发送心跳和报告结果。
- 员工不能自行批准重试或写入管理员验证记录。
- 每次领取任务都会获得独立租约令牌。报告和续租必须携带当前租约令牌；过期或旧令牌会被拒绝。

## 本地查看

服务启动后访问：

- 工作台：`http://127.0.0.1:8765/`
- 流程追踪：`http://127.0.0.1:8765/trace`

在流程追踪页面输入 `JARVIS_ADMIN_TOKEN`。令牌只保留在页面内存中，不写入 URL 或 localStorage；关闭页面后应重新输入。

## 重要注意

- 开发服务默认绑定 `127.0.0.1`。托管平台需要显式设置 `HOST=0.0.0.0`，并配置强随机 `JARVIS_ADMIN_TOKEN`；不要将无 TLS 的开发服务直接暴露到公网。
- 生产环境应使用 HTTPS、强随机令牌、密钥管理、速率限制、审计保留策略，并限制管理员访问网络。
- 当前存储是本地 JSON 文件，适合单实例 MVP；不适合多实例并发生产部署。
- 管理员写入的 `verification.accepted` 仅表示记录的检查结果被接受。系统始终将 `verified_truth` 保持为 `false`，不会把结构检查自动升级为事实证明。
