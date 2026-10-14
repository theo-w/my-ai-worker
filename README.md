# My AI Worker

JARVIS 数字分身与数字员工 MVP：以目标为中心动态组织员工、追踪执行状态、收集反馈，并对阻塞与结果验证保留审计记录。

## 本地启动与查看流程

需要 Python 3.12+；核心运行时不需要额外 Web 框架依赖。

```bash
git clone https://github.com/theo-w/my-ai-worker.git
cd my-ai-worker

# 仅用于本机模拟工作台；不要配置真实模型/搜索凭证
export JARVIS_PUBLIC_DEMO=true
python -m mvp.server
```

默认服务端口为 `8765`。启动后：

- 工作台：`http://localhost:8765/`
- **流程追踪与验收：`http://localhost:8765/trace`**
- 游戏体验原型：`http://localhost:8765/playtest`

纯模拟工作台不需要 Token，但不会启用工作流 API。要使用数字员工队列和流程追踪页，请关闭 `JARVIS_PUBLIC_DEMO`，配置管理员 Token 与员工 Token（见下方安全文档），然后在工作台/试玩页顶部或 `/trace` 页面输入管理员 Token。认证模式下，任务输入/输出、反馈、阻塞原因、重试次数、任务历史和全局事件时间线只对管理员开放。请勿将 Token 提交到代码库或通过不可信网络传输。

### 运行一次可验收的端到端流程

纯模拟模式只演示公开工作台，不开放员工队列 API。要验收分身/员工闭环，请先停止模拟服务器，在启动服务器的同一终端执行 `unset JARVIS_PUBLIC_DEMO`，再按 [安全与认证说明](docs/SECURITY_AND_AUTH.md) 配置管理员 Token、员工 Token 和员工能力，重新启动服务。随后在同一终端环境运行：

```bash
python -m mvp.demo_workflow
```

如需指定工作地址或员工，可设置 `JARVIS_BASE_URL`、`JARVIS_DEMO_WORKER_ID` 和 `JARVIS_DEMO_CAPABILITY`。脚本会创建一个演示任务、让指定员工领取并提交输出、记录结构化检查结果，最后打印任务 ID 和流程追踪页地址。它会明确标注模拟输出，不会伪装成真实市场研究，也不会把结构化检查通过当作事实正确。

## 运行配置

请在启动前配置管理员和员工凭证。示例变量名称及完整配置方式见 [安全与认证说明](docs/SECURITY_AND_AUTH.md)。监督器会回收过期租约；对明确阻塞的任务，系统默认要求分身显式决定是否重试。

## 当前能力与边界

- 数字分身可创建、检查和管理任务，员工通过领取、心跳、反馈和结果提交与分身协作；结果提交后先进入 `awaiting_validation`，验证记录通过后才会标记为完成。
- 每次领取有独立租约令牌，防止过期执行的迟到结果覆盖新一轮状态。
- 监控页展示运行时已记录的状态和事件；它不会凭空证明模型输出真实，也不会将 `completed` 自动等同于事实正确。
- 保守的临时故障策略是规则启发式，不是通用语义规划器；高影响操作仍需明确授权。
- 当前功能处于开发分支验证阶段，自动化测试通过也不代表已部署或完成真实模型端到端验收。

## 文档

- [数字分身与数字员工信息流图](docs/DIGITAL_TWIN_EMPLOYEE_FLOW.md)：目标、任务、反馈、独立验证、监控与递归改进的逻辑链路。

- [流程可观测性与验收](docs/OBSERVABILITY.md)
- [目标驱动架构](docs/GOAL_DRIVEN_ARCHITECTURE.md)
- [整体逻辑流程：规则与 LLM 生效时机](docs/WORKFLOW_AND_LLM_TIMING.md)
- [安全与认证](docs/SECURITY_AND_AUTH.md)
- [手动验收清单](docs/MANUAL_ACCEPTANCE.md)：按步骤查看任务创建、员工领取/反馈、结果验证和阻塞处理。
- [递归自我改进](docs/RECURSIVE_SELF_IMPROVEMENT.md)：执行复盘、基准评估、回归拦截与人工晋级边界。
