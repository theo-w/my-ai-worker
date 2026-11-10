# 未来两周:按 ROI 的修复清单

> 生成日期:2026-11-09。评估角度:产品经理 + 唯一真实用户(你自己)。
> 预算:4–6 小时,业余项目。未 commit;先确认再动手。

## 结论

这是一个**自己用、demo 级**的执行底座。它没"接真模型/真调研",也不打算把——`build_search_provider` 对不可访问源直接拒绝,比假成功好。
所以两周目标不是"补功能",而是**让文档/测试跟现实**,再决定"每周不到两次跑它"算不算砍。

## 先修(P0,约 1.5h)

### P0-1 三个失败测试:文案改成通用中文,断还英文

`python3 -m pytest mvp -q` → **3 failed, 291 passed**。

| 测试 | 问题 |
| --- | --- |
| `mvp/test_mvp.py::test_demo_mode_allows_labeled_handoff_without_real_evidence` | 断 `"demo only"`,实际文案 `产品原型冲刺(仅演示)` |
| `mvp/test_workflow_stepper.py::test_business_journey_shows_real_research_design_and_feasibility_stages` | 断 `"玩法假设"` 等游戏标签,dashboard 改通用产品/用户视角 |
| `mvp/test_live_research_pipeline.py::test_live_research_without_provider_is_explicitly_unavailable` | 断 `"no real research"`,实际 `未配置真实搜索服务,未执行真实调研。` |

**修**:更新测试到当前中文文案。不改产品代码——"模拟/未配置"标注是设计。

### P0-2 文档跟现实不符

| 文件 | 说 | 实际 |
| --- | --- | --- |
| `docs/COMPARISON_MATURE_PROJECTS.md` | 291 全绿;55/55 ✅ | 3 失败;`docs/GLOSSARY.md` 仍列待实现 |
| `docs/SPEC_TRACEABILITY.md` | 幂键/证据链 ✅ | 部分条目 🔲,与"已补"矛盾 |

**修**:重生成矩阵后 P0-1 绿;`GLOSSARY.md` 待实现项保留,别删。

## 再修(P1,约 2h)

### P1-1 独立验证算核心,别让它空地

`docs/DIGITAL_WORKFORCE_PROTOCOL.md` 与 `verification.py` 只做**结构检查**。
"结果验证通过 ≠ 事实正确"对文档都承认。

**修**:把 `docs/OBSERVABILITY.md` 与 dashboard 文案明讲:验证只证明"结构完整",不证明事实。
**别**:把这算 blocker。没真模型,永远不能验证事实——接受。

### P1-2 两个用例都薄,选一个

- **游戏可行性**:文档链真(`docs/mvp-zelda-to-original-game-test.md`),但 Reddit/Steam 不可访问。
- **用户研究**:只在 `mvp/dashboard.html` 文案,没接线。

**修**:选游戏可行性作唯一验收用例;用户研究文案改成"复用同一薄副本",别建第二管道。

## 可选(P2,约 1h)

### P2-1 每次刷新重粘 admin Token

`mvp/dashboard.html` 已有"在此设备记住"(localStorage);`mvp/trace.html` **故意不持久**。
`test_workforce_api_integration.py::test_trace_dashboard_is_served_without_exposing_workforce_data`
断 trace.html 不含 `localStorage.setItem`——加持久化会破测试,属设计不算 bug。

**修**:无。dashboard 已满足;trace 保持内存中 Token,别改。

## 砍标准

**每周不到两次跑它 → 不建。** 其余问题(架构、跟 CrewAI/MetaGPT 比)不重要。
先跑 P0-1+P0-2,再按"自己是否真周两次用"决定继续。
