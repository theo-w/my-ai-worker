# 术语表

> 统一项目中的核心术语，消除 "Digital Employee" / "Digital Worker" 混用问题。

---

## 核心术语

### Digital Twin（数字分身）

**定义：** 意图解释、任务分解、执行模式选择、监督决策、最终验收的分身层。是闭环控制器，不是简单的任务分发器。

**代码对应：**
- `mvp/twin.py:DigitalTwin` — 策略层，负责团队组建和执行模式选择
- `mvp/twin.py:AutonomousProjectLoop` — 有界迭代循环
- `mvp/twin.py:DigitalTwinCoordinator` — API 层面的分身控制器

**职责：**
1. 接收用户目标，解释意图，制定成功标准和约束
2. 判断单代理是否足够，必要时拆分任务
3. 选择执行模式（单代理 / 团队 / 独立审查）
4. 监督执行过程，处理阻塞和失败
5. 对员工结果进行论证：检查来源可靠性、依据可溯源
6. 做出最终验收决策

**规范来源：**
- `DIGITAL_WORKFORCE_PROTOCOL.md` §2 Core responsibilities
- `DIGITAL_TWIN_EMPLOYEE_FLOW.md` 协作流程图
- `GOAL_DRIVEN_ARCHITECTURE.md` §1 Design decisions

---

### Digital Employee（数字员工）

**定义：** 接受任务、心跳保活、提交结构化结果的执行者。身份从 token 派生，能力由服务端分配，不可自赋。

**代码对应：**
- `mvp/worker_agent.py:DigitalEmployeeAgent` — 独立进程运行的员工代理

**职责：**
1. 领取符合自身能力的任务
2. 定期发送心跳证明存活
3. 提交结构化结果，附带证据引用
4. 遇到阻塞时上报原因，不静默失败

**规范来源：**
- `DIGITAL_WORKFORCE_PROTOCOL.md` §2 Core responsibilities
- `DIGITAL_WORKFORCE_PROTOCOL.md` §4 Worker feedback contract

**术语说明：** 代码和文档中曾混用 "Digital Worker"，现统一为 "Digital Employee"，与项目名 JARVIS 的"员工"概念一致。

---

### Workforce（员工队列）

**定义：** 任务队列、租约管理、事件流的运行时基础设施。是 Digital Twin 和 Digital Employee 之间的中间层。

**代码对应：**
- `mvp/workforce.py:WorkforceRegistry` — 任务队列实现

**职责：**
1. 持久化任务和事件
2. 管理租约令牌（防过期结果覆盖）
3. 回收过期租约
4. 维护追加式事件历史
5. 提供队列快照

**规范来源：**
- `DIGITAL_WORKFORCE_PROTOCOL.md` §3 Task lifecycle
- `DIGITAL_WORKFORCE_PROTOCOL.md` §5 可靠性要求
- `OBSERVABILITY.md`

---

### Evidence Chain（证据链）

**定义：** 从员工提交到分身验收的完整可追溯链路。每个环节都有结构化记录。

**阶段二 §2.5 原则：**
1. **可追溯性：** 结论必须附带来源 URL、标题、原始摘录
2. **原始数据客观性：** 保留原始摘录，标注来源类型
3. **来源可靠性论证：** 检查 HTTPS、来源类型、时间、对立来源
4. **依据可溯源：** 决策记录证据 ID、忽略原因、不确定性
5. **不可伪造性：** awaiting_validation 后员工不可修改
6. **模拟与真实标注：** 所有输出标注 simulated 字段

**规范来源：**
- `DIGITAL_WORKFORCE_PROTOCOL.md` §2.5（阶段二新增）
- `docs/schemas/evidence.json`

---

### MVP（最小可验收产品）

**定义：** 第一个可验收的垂直切片。以 AI 原生游戏可行性为第一个用例，协议本身保持领域无关。

**范围：**
- ✅ 任务队列、租约管理、心跳、事件历史
- ✅ 数字分身目标分解和监督
- ✅ 数字员工领取执行和结果提交
- ✅ 证据门禁和验证
- ✅ 可观测性（监控、Trace 页面）
- ✅ 递归自我改进护栏
- ❌ 生产级语义规划器（待实现）
- ❌ 真实模型/搜索端到端验收（待实现）
- ❌ 多实例生产部署（当前为单实例 JSON 存储）

**规范来源：**
- `DIGITAL_WORKFORCE_PROTOCOL.md` §100 Delivery sequence
- `GOAL_DRIVEN_ARCHITECTURE.md` §Honest MVP boundary

---

## 辅助术语

### Lease Token（租约令牌）

每次任务领取时生成的 fencing token，用于防止过期结果覆盖新状态。报告和续租必须携带当前令牌。

### Provenance（来源溯源）

记录执行器类型（simulated / llm / live_search）和使用的工具链。

### Simulation（模拟模式）

当未配置真实搜索/LLM 提供商时，系统使用确定性模拟输出。模拟输出必须标注 `simulated: true`，不得进入证据链。

### Evidence Gate（证据门禁）

验证输出是否包含至少一个结构有效的非模拟来源记录。通过门禁不等于事实证明。

### Verified Truth（已核实事实）

系统始终将此字段保持为 `false`。结构检查通过不等于事实证明。

## 术语澄清（有意选择，非缺口）

- **词级 bigram 检索**：`game_knowledge.py` 用词级/中文 bigram 词权重，不是向量库。这是有意选择（零依赖、可审计），非遗漏。
- **任务邮箱 + 能力路由**：员工通过轮者领取/心跳/反馈/结果提交协作，无 agent-to-agent 消息传递。措辞已改为「任务邮箱 + 能力路由」。
