# JARVIS MVP 手动验收清单

本清单用于在本机实际查看分身/员工任务流。先按 [安全与认证配置](SECURITY_AND_AUTH.md) 配好管理员和员工 Token，再启动服务。建议只在本机测试，并使用单独的测试数据文件。

## 1. 启动和打开流程追踪页

```bash
export HOST=127.0.0.1
export PORT=8765
export JARVIS_ADMIN_TOKEN='你的管理员令牌'
export JARVIS_WORKER_TOKENS='{"researcher":"你的researcher令牌"}'
export JARVIS_WORKER_CAPABILITIES='{"researcher":["research"]}'
export JARVIS_WORKFORCE_STORE='./data/acceptance-workforce.json'
python -m mvp.server
```

浏览器打开 `http://127.0.0.1:8765/trace`，输入管理员令牌。页面默认每 5 秒刷新，也可手动刷新。任务详情应展示输入、执行状态、员工输出、反馈、阻塞原因、验证记录和任务历史。

## 2. 创建一个可追踪任务

在另一个终端执行（需要 `curl` 和 `jq`）：

```bash
BASE='http://127.0.0.1:8765'
TASK_JSON=$(curl -fsS -X POST "$BASE/api/workforce/tasks" \
  -H "Authorization: Bearer $JARVIS_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"验证 AI 原生游戏需求假设","description":"检查目标玩家、来源质量与反例","capability":"research","priority":5}')
echo "$TASK_JSON" | jq .
TASK_ID=$(echo "$TASK_JSON" | jq -r '.task.id')
```

回到流程追踪页面刷新，应看到一个排队中的任务。若未出现，检查管理员 Token、服务地址和服务端日志。

## 3. 模拟员工领取并回报结果

下面是通过真实 HTTP API 进行的可控验收，不会自动调用外部模型或网络研究服务。员工输出明确标记为验收样例。

```bash
CLAIM=$(curl -fsS -X POST "$BASE/api/workforce/claim" \
  -H "Authorization: Bearer $RESEARCHER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"capabilities":["research"]}')
echo "$CLAIM" | jq .
LEASE=$(echo "$CLAIM" | jq -r '.task.lease_token')

curl -fsS -X POST "$BASE/api/workforce/report" \
  -H "Authorization: Bearer $RESEARCHER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$TASK_ID\",\"status\":\"completed\",\"lease_token\":\"$LEASE\",\"output\":\"[ACCEPTANCE SAMPLE] 待验证假设；尚未检索外部来源。\",\"blocker\":\"\"}" | jq .
```

回到页面查看任务详情与历史。该输出是验收样例，不是市场研究结论；它不包含可验证来源，也不应被视为事实。

## 4. 记录结构检查结果

管理员可记录明确的验证结果。这里的检查只验证记录能否被持久化，不声称内容是真实事实：

```bash
curl -fsS -X POST "$BASE/api/workforce/verify" \
  -H "Authorization: Bearer $JARVIS_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$TASK_ID\",\"verification\":{\"accepted\":false,\"status\":\"rejected\",\"checks\":[{\"name\":\"source_evidence_present\",\"passed\":false,\"note\":\"验收样例没有外部来源\"}]}}" | jq .
```

页面应显示验证状态为 rejected，且 `verified_truth` 为 `false`。这体现了“员工完成提交”和“结果通过验证”是两个不同阶段。

## 5. 验收阻塞与重试边界

可创建另一个任务，领取后用 `status=blocked` 报告阻塞原因。页面应显示任务阻塞、原因和员工报告历史。普通员工不能调用管理员重试/验证操作；只有管理员或分身策略经服务端校验后，才可批准有上限的重试。

## 6. 通过标准

- [ ] 管理员 Token 才能读取全局任务/员工状态。
- [ ] 新建任务出现在流程追踪页，并能自动刷新。
- [ ] 领取任务会生成租约令牌；缺失或旧令牌不能提交结果。
- [ ] 任务详情显示员工输入、输出、反馈和历史事件。
- [ ] 阻塞任务不会被默认自动重试。
- [ ] 验证记录持久化，并将 `verified_truth` 保持为 `false`。
- [ ] 能明确区分真实执行、验收样例、模拟输出和独立验证结果。

## 7. 当前限制

这份清单验证 API、持久化和可观测 UI 的连通性。它不等于真实模型端到端验收，也不会自动创建外部研究证据。完成后可再接入有凭证的模型/搜索适配器，验证真实执行过程。
