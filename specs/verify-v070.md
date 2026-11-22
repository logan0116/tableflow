# v0.7.0 验证报告（T9 整体评审，019–025）

- 评审人：reviewer（T9 初审 → t13 复评）；初审 2026-11-22 18:18，复评 2026-11-22 18:45（Asia/Shanghai）
- 评审基准（队长裁定）：**本地当前源码（交付物）+ 迁移后线上库只读快照副本**；写操作只落副本。线上容器仍是 `tableflow:0.6.5` 旧镜像，其差异不计缺陷，单列「部署后需复验」。
- 基线：HEAD `fd4b841`；契约 `board@4.yaml` sha256 `2e499bdb…47da`；线上快照 sha256 `c54640be…931b`（与容器内 backup 一致）；迁移前备份 sha256 `14706468…4f1c`。
- 证据目录：`.tmp-shots/review-v070/`（env/us1…us6/ui/skills/snapshot/scripts/logs；逐条命令与产物可复跑）。

## 一、结论（t13 复评后最终版）

**按 150 条 Acceptance Scenario 判定：通过 150 / 未通过 0 / 待部署复验 5 项 / 已知边界 1 项（另列 1 条已知数据偏差）。**

| 规格 | AS | 通过 | 未通过 | 一句话 |
|---|---|---|---|---|
| 019-test-contract | 27 | 27 | 0 | 六表结构、派生、执行进度、六节点、迁移、门禁全部实测通过 |
| 020-protocol-test | 23 | 23 | 0 | 状态/结果一致、两步写入、重复纳入、行 id/case_no 全通过（pytest 20 条 + HTTP 黑盒） |
| 021-case-view | 15 | 15 | 0 | 用例视图/版本行三列弹层/明细/失效行/空弹层全部通过（空弹层经 t12 修复后复评） |
| 022-role-view | 22 | 22 | 0 | 四角色通栏、3/4/4/5 页签矩阵、配色变量、持久化、键盘/吸附全通过 |
| 023-cell-compute | 18 | 18 | 0 | and 条件项类型/取值域校验、stage_done/gate 联动、既有口径不回归全通过 |
| 024-role-skills | 28 | 28 | 0 | 六技能行为通过；`--apply` 经 t11 补齐后 9 条 AS 按字面命令复跑通过 |
| 025-version-stage | 17 | 17 | 0 | 串行/闸门一致性、空集放行、不回退下游、stage_done/gate 全通过 |
| **合计** | **150** | **150** | **0** | 暂无未通过项（t9 的 D-01/D-02 均已修复并复评） |

**版本判断：v0.7.0 的 019–025 全部通过验收。** 放行前只剩两件事：按第八节做**部署后 5 项复验**（线上仍跑 0.6.5），以及知悉 N1 语义边界与 6/8 项目 indep id 漂移的适用范围。t9 初审的 10 条未通过（D-01 9 条 / D-02 1 条）已在 t11/t12 修复，详见第十四节「复评记录」。

## 二、验证基线（可复现）

| 项 | 结果 | 证据 |
|---|---|---|
| 全量 pytest | **201 passed, 1 warning**（7.71s） | `env/pytest-final.log` |
| 本轮新增套件 | 45 passed（020/023/025/迁移） | `env/pytest-new-suites.log` |
| 门禁（本地新代码 + 快照副本） | 8 项目 / 48 表 / 632 字段实例，**差异 0（exit 0）** | `us6/gate-local-final.json` |
| 门禁（模板产物） | **差异 0（exit 0）** | `us6/gate-template-final.json` |
| 门禁负例：缺 run 表 | exit 1，40 条，含「关系目标表 run 不存在」 | `us6/gate-missing-run.json` |
| 门禁负例：board@3 库 | exit 1，48 条，逐字段列出差异 | `us6/gate-board3.json` |
| 门禁对线上旧 API | exit 1，**48 条表级 kind 缺失（8×6）**，旧镜像导致，按基准不计缺陷 | `us6/gate-live-oldapi.json` |
| 前端构建 | `npm run build` exit 0 | `ui/build.log` |
| 独立结构校验 | 0 issues（8 项目） | `us1/check-final.json` |
| 写侧黑盒 | **21/21 通过** | `us3/write-scenarios.json` |
| 迁移验证 | AS1/AS2/AS3 全通过 | `us5/us5-report.json` |
| 技能故障注入 | 4/4 通过 | `skills/client-fault-injection.json` |
| 界面观测 | 角色矩阵/变量/持久化/弹层/失效行/仅明细项目 | `ui/ui-checks.json`、`ui/*.png` |

## 三、019 契约六个 User Story（27/27）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 六表字段数/名/类型/顺序 | 通过 | `us1/check-final.json` 0 issues；门禁 0 |
| US1-AS2 8 条 relation 边、表对唯一 | 通过 | 同上（边集与契约一致，run 无反向字段） |
| US1-AS3 run kind=detail、不进导航、按 id 可读 | 通过 | 本地 API kind=detail；`ui-checks` 全局 5 页签无 run；`GET run 行` 200 |
| US1-AS4 case 行 id 格式 + 规格可在 indep 找到 | 通过 | 10 条 019-US* 行；结构校验 0；`us1/check-after-cases.json` |
| US2-AS1 派生 N 条、id=场景号、indep 指向来源 | 通过 | `skills/test-plan-apply-1.json`：019 派生 27 条、指向 019-AR |
| US2-AS2 二次派生新建 0，变更就地更新 | 通过 | 第二次 `created_cases=0/created_runs=0`；夹具改步骤 `updated_cases=1` |
| US2-AS3 删场景报「源场景已不存在」 | 通过 | `skills/fixture-derive-2.json`：orphans=`099-US1-AS3` |
| US2-AS4 多版本 run 不受用例更新影响 | 通过 | `v9.9.1` 3 条 run 仍为 todo、无步骤副本；`us5/skills.db` |
| US3-AS1 纳入=建 run+追加 ver.runs、回读可见 | 通过 | `us3/write-scenarios.json` US3-AS1 |
| US3-AS2 10 纳入 4 执行 → 10/4/否 | 通过 | 同上 US3-AS2 |
| US3-AS3 全执行 → 10/是，fail 不改三字段 | 通过 | 同上 US3-AS3 |
| US3-AS4 state=todo 写 result → 400 且不变 | 通过 | 同上 US3-AS4（错误文本见证据） |
| US3-AS5 空集 0/0/真 | 通过 | 同上 US3-AS5 |
| US3-AS6 重复纳入 → 400 或复用，不产生第二条 | 通过 | 同上 US3-AS6（400 + 清单计数 1） |
| US4-AS1 跳级置 done → 400，指出前序 | 通过 | 同上 US4-AS1 |
| US4-AS2 用例未全执行置「测试」→ 400 | 通过 | 同上 US4-AS2 |
| US4-AS3 缺陷未清零/变更未通过置「测试验收」→ 400 | 通过 | 同上 US4-AS3（两条错误分别指名缺陷/变更） |
| US4-AS4 规格未验收置「开发验收」→ 400 | 通过 | 同上 US4-AS4 |
| US4-AS5 failed 阻断、返工后可推进 | 通过 | 同上 US4-AS5 |
| US4-AS6 六节点全 done → stage_done/gate 真；退回转假 | 通过 | 同上 US4-AS6 / 025-US3-AS3；依赖 023 已落地 |
| US5-AS1 新增两表+版本表 11 字段，老表不变 | 通过 | `us5-report.json`：16 新表、ver 15→26、245 行比对 0 值差异、0 结构差异、16 条契约改名 |
| US5-AS2 released 六节点 done/gate 真；planned todo | 通过 | 同上：released 36/36、planned/dropped 18/18 |
| US5-AS3 中途失败重跑幂等、不覆盖 | 通过 | 同上：两次迁移 exit 0；删 run 表+stage_done 字段后重跑 exit 0，结构与数据与完整迁移一致 |
| US6-AS1 全部项目门禁差异 0 | 通过 | `us6/gate-local-final.json` 0；含表名/kind/关系列/闸门标记 |
| US6-AS2 缺 run 表被指出 | 通过 | `us6/gate-missing-run.json` exit 1 |
| US6-AS3 board@3 版本表 15 字段被逐字段列出 | 通过 | `us6/gate-board3.json` exit 1 |
| US6-AS4 模板产物差异 0 | 通过 | `us6/gate-template-final.json` |

适用范围说明：US1-AS4 的「规格号↔indep 行」映射**仅 tableflow 成立**（indep 行 `001-AR…025-AR`）；其余 6 个项目 indep 行 id 形态不同（见第十节），本轮不派生，不据此判失败。

## 四、020 写协议（23/23）

pytest `backend/tests/test_run_protocol_020.py` 20 条 + 本报告 HTTP 黑盒（`us3/write-scenarios.json`）。

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 todo+空 result → 200 | 通过 | `test_create_todo_without_result_ok`；US3-AS1 HTTP |
| US1-AS2 todo+result → 400 零写 | 通过 | `test_create_todo_with_result_rejected_zero_write`；US3-AS4 HTTP |
| US1-AS3 done+空 result → 400 | 通过 | `test_create_done_without_result_rejected_zero_write` |
| US1-AS4 只给 result 不给 state → 400 | 通过 | `test_create_result_without_state_rejected` |
| US1-AS5 只 PATCH state=done → 400 整行不变 | 通过 | `test_patch_state_done_without_result_rejected` |
| US1-AS6 同请求 state+result → 200 回读一致 | 通过 | `test_patch_state_done_with_result_ok` |
| US1-AS7 存量不一致行：无关字段 400，自洽改 200 | 通过 | `test_patch_fix_inconsistent_legacy_row_in_one_request` |
| US2-AS1 POST run → 200、可按 id 读 | 通过 | HTTP US3-AS1；`us3/write-scenarios.json` |
| US2-AS2 第二步引用不存在 run → 400 版本零写 | 通过 | HTTP 020-US2-AS2/AS3 |
| US2-AS3 第二步失败后第一步可回读 | 通过 | 同上（回读 state=done） |
| US2-AS4 修正引用后 PATCH → 200 | 通过 | 本次复跑：bad_ref 400 → fixed 200，`tf-v-runs` 含该 id |
| US2-AS5 重放第一步 → 400，不产生第二条 | 通过 | 复跑 replay_create=400；run 表仅 1 行 |
| US3-AS1 重复 POST → 400 指明已纳入 | 通过 | `test_duplicate_inclusion_second_post_is_400_and_single_row`；HTTP US3-AS6 |
| US3-AS2 已纳入后重放第一步 → 400 | 通过 | `test_duplicate_after_inclusion_is_400` |
| US3-AS3 runs 含重复 id → 400 零写 | 通过 | HTTP 020-US3-AS3/AS4 |
| US3-AS4 挂别的版本 run → 400 零写 | 通过 | 同上 |
| US3-AS5 重跑就地更新、行数与 runs 不变 | 通过 | 复跑 rerun_patch=200；`tf-v-runs` 不变 |
| US4-AS1 行 id 非 `<版本号>--<用例号>` → 400 | 通过 | HTTP 020-US4-AS1/AS2 |
| US4-AS2 case_no 与行 id 后缀不一致 → 400 | 通过 | 同上 |
| US4-AS3 普通表 state/result 字面不套协议 | 通过 | `test_non_run_table_with_state_result_names_is_untouched` |
| US4-AS4 非惯例字段 id 按值域识别仍 400 | 通过 | `test_run_table_detected_by_value_domain_not_field_id` |
| US4-AS5 非惯例字段 id 仍校验行 id 形状 | 通过 | `test_run_table_detected_by_value_domain_still_enforces_row_id` |
| US4-AS6 case_no 按名称兜底识别 | 通过 | `test_case_no_fallback_by_field_name` |

## 五、021 用例视图（15/15）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 六表项目导航 5 页签、无执行情况表 | 通过 | `ui-checks.json` 全局矩阵；截图 `ui/role-test.png` |
| US1-AS2 测试用例页签列头/行数 | 通过 | `ui-checks.json`：8 列、10 行；`ui/case-view-test-role.png` |
| US1-AS3 board@3 项目缺 kind 仍显示 | 通过（代码走查） | `table-kind.ts`：`kind !== "detail"`，缺失按 board；接口旧库默认 board |
| US1-AS4 仅 detail 表项目显示暂无表格 | 通过 | 造 `p-detailonly` 项目：`暂无表格 当前项目下还没有任何表格。`，tabs=[] |
| US1-AS5 切项目默认第一张 board 表 | 通过 | 切项目后 active=版本管理；角色隐藏 case 时自动回版本管理 |
| US2-AS1 点击版本行 runs → 三列弹层、标题项数 | 通过 | `ui-checks.json`：`关联条目 · 10 项`，编号/用例号/执行状态 |
| US2-AS2 三列内容 = run id / case_no / state 标签 | 通过 | 同上；含 `已执行`/`待执行` 两种标签 |
| US2-AS3 todo 显示未执行标签、不出现 result | 通过 | v9.9.8 弹层第三列 `待执行`；无 result 列 |
| US2-AS4 点行开明细、结果可读 | 通过 | `关联明细 · v9.9.9--019-US1-AS1`，执行结果=通过 |
| US2-AS5 空 runs → 「0 项」空弹层 | 通过（t12 修复后复评） | 单元格按钮「0 项」title=`关联条目 · 0 项`；弹层「关联条目 · 0 项」+「暂无关联条目」；`rerun/ui-d02.json`、`rerun/d02-empty-modal.png` |
| US2-AS6 失效 run 标「关联已失效」不可点 | 通过 | 删 run 行后：`relation-row is-missing`、第二列「关联已失效」、cursor default |
| US2-AS7 未配 display/status 回退只显示编号 | 通过（代码走查） | `RelationListModal.tsx` 按 options 条件渲染列，不猜列名 |
| US3-AS1 其他三张 relation 弹层不变 | 通过 | `git status frontend/src`：未改 RelationModal；弹层列头与 006/017 一致 |
| US3-AS2 导航隐藏只读 kind，无表名/表 id 硬编码 | 通过 | `table-kind.ts` 仅判 kind；源码 grep 无 `用例执行情况`/`tf-run` 判断 |
| US3-AS3 未改表格结构色 | 通过 | `git diff styles.css` 仅新增角色变量注释，无结构色令牌改动 |

## 六、022 角色视图（22/22）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 42px 通栏、四入口、当前角色名 | 通过 | `ui-checks.role_bar` |
| US1-AS2 点软件测试：白底高亮、aria-pressed、角色名/徽章 | 通过 | bg=`rgb(255,255,255)`、aria-pressed=true、`当前角色 软件测试`、徽章同步 |
| US1-AS3 通栏吸附 | 通过 | computed `position=sticky`、top=0 |
| US1-AS4 键盘 Tab/Enter 切换、可见聚焦环 | 通过 | 聚焦「软件开发」outline=`rgb(255,255,255)`，Enter 后角色切换 |
| US2-AS1 系统工程 3 页签 | 通过 | `ui-checks.nav_tabs_by_role.systems` |
| US2-AS2 软件开发 4 页签 | 通过 | 同上 dev |
| US2-AS3 软件测试 4 页签（ver/case/dep/bug） | 通过 | 同上 test（t10 后映射） |
| US2-AS4 全局 5 页签、无执行情况表 | 通过 | 同上 all |
| US2-AS5 在用例表切开发 → 自动回版本管理 | 通过 | `ui-checks.switch_from_case_to_dev` |
| US2-AS6 角色隐藏的表仍可经弹层读 | 通过 | 软件测试角色下 v0.6.5 独立需求弹层读到 018-AR/已验收 |
| US2-AS7 非六表合同表保留导航 | 通过（代码走查） | `roles.ts`：语义键为 null 的表对所有角色保留 |
| US3-AS1 系统工程四变量 | 通过 | `#0b5cab/#08407a/#ddf4ff/#f7fbff` |
| US3-AS2 软件开发四变量 | 通过 | `#1a7f37/#0f5323/#dafbe1/#f7fdf9` |
| US3-AS3 软件测试四变量 | 通过 | `#9a6700/#7d5300/#fff6de/#fdfbf4` |
| US3-AS4 全局四变量 | 通过 | `#57606a/#24292f/#eef1f4/#f6f7f9` |
| US3-AS5 结构色五令牌跨角色不变 | 通过（3/4 角色五令牌实测，全局三项实测） | dev/systems/test 均 `#c9d1d9/#e1e6ec/#edf1f4/#e3eefb/#f3f6f9`；全局 border/header/zebra 相同；结构令牌来自同一 CSS 块（代码走查） |
| US3-AS6 enum 标签色来自自身 tone | 通过 | 系统工程下 enum bg=`rgb(238,241,244)`（neutral），非角色色 |
| US4-AS1 刷新后保持软件测试 | 通过 | reload 后 role=软件测试、4 页签、仓库值 `test` |
| US4-AS2 重新打开仍系统工程 | 通过（存储值 + 同一实现路径；见 D-03） | 切系统工程后存储 `systems`；reload 持久化路径用 software-test 实测保持 |
| US4-AS3 非法存储值回退全局 | 通过 | 写入 `not-a-role` 刷新 → 全局、5 页签、无报错 |
| US4-AS4 localStorage 禁用/写失败仍生效本会话 | 通过（代码走查） | `useRole.ts` 读写 try/catch，失败回退内存态 |
| US4-AS5 只存角色 id | 通过 | 值 `test/systems/dev`，无业务数据 |

## 七、023 计算表达式（18/18）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 六节点全 done → true 且落库 | 通过 | HTTP US4-AS6；`test_a_and_enum_done_true_and_false` |
| US1-AS2 任一 doing/todo → false | 通过 | `test_a_and_enum_done_true_and_false` |
| US1-AS3 failed ≠ done → false | 通过 | `test_a_and_enum_done_true_and_false`（failed 用例） |
| US1-AS4 节点 null → false | 通过 | `test_c_and_of_computed_condition_and_gate_override`/`test_a_and_*` |
| US1-AS5 gate=and(stage_done==true) 联动 | 通过 | HTTP US4-AS6 true；025-US3-AS3 退回转假 |
| US2-AS1 枚举 == 5/true → 400 不落库 | 通过 | HTTP 023 检查：`枚举字段只能等于字符串取值` |
| US2-AS2 枚举 == "Done" → 400 列取值 | 通过 | HTTP：`不是枚举字段「优先级」的取值：Done（可选：P0、P1、P2）` |
| US2-AS3 number == "2" → 400；==2 成功 | 通过 | HTTP：`数字字段只能等于数字`；合法 `scenes==0` 200 落库 |
| US2-AS4 布尔条件 ==1 → 400 | 通过 | `test_d_invalid_conditions_rejected_without_persistence` |
| US2-AS5 relation 作条件 → 400 | 通过 | HTTP：`关联值是行 id 数组，无法与单个取值比较` |
| US2-AS6 结构非法条件 → 400 不落库 | 通过 | `test_d_invalid_conditions_rejected_without_persistence` |
| US3-AS1 既有布尔/数字条件不回归 | 通过 | `test_c_existing_bool_and_number_conditions_unchanged` |
| US3-AS2 引用同表计算字段按有效值/拓扑序 | 通过 | `test_c_and_of_computed_condition_and_gate_override` |
| US3-AS3 依赖成环 → 400 | 通过 | `test_c_and_of_computed_condition_and_gate_override`（环） |
| US3-AS4 gate 人工覆盖 → 400 回滚 | 通过 | HTTP：`闸门字段「发布条件」禁止人工覆盖`，override_meta=false |
| US3-AS5 写事务内重算落库 | 通过 | `test_b_enum_condition_follows_writes` |
| US4-AS1 无中间布尔字段 | 通过 | 结构快照 ver 26 字段，无多余 stage 中间字段；gate/stage_done 直接 and |
| US4-AS2 六节点全 done 真、任一非 done 假 | 通过 | HTTP US4-AS6；`test_gate_turns_false_after_node_rollback` |

## 八、024 角色技能（28/28）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 六技能 dry-run 零写入 | 通过 | `skills/dry-*.json`：dev-plan/test-plan success writes skipped；其余 4 个按设计 failed、writes 空；无审计新增 |
| US1-AS2 dev-plan 只解析 3 表 | 通过（代码走查） | `_tf_common.ALLOWED` + 运行成功；越权读会 SkillFailure |
| US1-AS3 test-check 只解析 4 表、只写版本节点 | 通过（代码走查） | `tf_test_check.py` ALLOWED 与写入目标 |
| US1-AS4 六目录含 SKILL.md/scripts、无数据库驱动 | 通过 | 目录检查；`grep sqlite3/psycopg/sqlalchemy` 无命中 |
| US2-AS1 写后 readback 一致才 success | 通过 | `skills/test-implement-one.json` 含 readback |
| US2-AS2 503 → unknown 回读一致按成功 | 通过 | `client-fault-injection.json` case1 |
| US2-AS3 400 → failed 不重试 | 通过 | 同上 case2（attempts=1） |
| US2-AS4 200 非 JSON → unknown 回读定案 | 通过 | 同上 case3 |
| US2-AS5 unknown 退避 3 次仍 unknown、非 0 退出 | 通过 | 同上 case4（attempts=4、exit 非 0） |
| US3-AS1 派生 N 条、id=场景号、来源正确 | 通过（t11 修复后复评） | t11 修复后按字面 `--apply`：27 case/27 run，id=场景号，来源 019-AR（`rerun/d01-results.json`） |
| US3-AS2 二次派生 0/0、变更就地更新 | 通过（t11 修复后复评） | 字面 `--apply`：created 0/0、updated 1（`rerun/d01-results.json`） |
| US3-AS3 删场景报 orphans | 通过（t11 修复后复评） | 字面 `--apply`：orphans=`019-US9-AS1` 且未删除（`rerun/d01-results.json`） |
| US3-AS4 每条用例建 run+todo+ver.runs、无 plan 表 | 通过（t11 修复后复评） | 字面 `--apply`：27 run 全 todo、ver.runs=27、无计划表（`rerun/d01-results.json`） |
| US3-AS5 第 1 节点未 done → failed 零写入 | 通过（t11 修复后复评） | 字面 `--apply` exit 1：前序未 done、writes=0（`rerun/d01-results.json`） |
| US4-AS1 未勾任务 → failed 列任务、零变更 | 通过（t11 修复后复评） | 字面 `--apply` exit 1：列未完成任务、writes=0、开发节点不变（`rerun/d01-results.json`） |
| US4-AS2 任务全完成 → implement/dev 读回 done | 通过（t11 修复后复评） | 字面 `--apply`：dev=done、implement=done 读回一致（`rerun/d01-results.json`） |
| US4-AS3 规格未 accepted → failed 不推进开发验收 | 通过（t11 修复后复评） | 字面 `--apply` exit 1：列 099-AR pending、writes=0、开发验收不变（`rerun/d01-results.json`） |
| US4-AS4 规格全 accepted + dev done → dev_accept done | 通过（t11 修复后复评） | 字面 `--apply`：dev_accept=done（`rerun/d01-results.json`） |
| US5-AS1 执行用例写 done/pass/证据/执行人并回读 | 通过 | `skills/test-implement-one.json`：row done/pass/证据/执行人/时间 |
| US5-AS2 state=todo 给 result → 客户端先拒绝 | 通过（代码走查） | `_tf_common.write` 前校验 + 服务端 400 路径（020 US1-AS4） |
| US5-AS3 全部 done → 测试节点 done | 通过 | 本次实测 27/27 done 后 `测试=done` 200；技能 dry-run 仅前置校验 |
| US5-AS4 缺陷未 closed → failed 列缺陷、节点不变 | 通过 | `skills/test-check-bug-open.json`：`缺陷未关闭：['BUG-RV-9']`、writes 0 |
| US5-AS5 用例全执行/缺陷清/变更 passed → test_accept done + stage_done 真 | 通过 | `skills/test-check-apply.json`：测试验收=done、stage_done=true、gate=true |
| US5-AS6 输出不含 key 值 | 通过 | 以 `TF_API_KEY=SECRET_RV_123` 运行，输出匹配 0 次 |
| US6-AS1 满足前置节点 dry-run 输出 plan、exit 0、零写入 | 通过 | `dry-tf-dev-plan.json`/`dry-tf-test-plan.json`（writes skipped） |
| US6-AS2 不满足前置 dry-run failed 零写入 | 通过 | `dry-tf-dev-check.json`/`dry-tf-test-check.json`（writes 0） |
| US6-AS3 无 TF_BASE → 立即 failed 提示 | 通过 | `skills/dry-no-base.json`：`未设置 TF_BASE（看板实例地址），拒绝运行` |

## 九、025 六节点（17/17）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 跳级到第 2 节点 → 400 零写 | 通过 | `test_skip_node_rejected_zero_write`；HTTP US4-AS1 |
| US1-AS2 第 4 节点从 todo 直 done → 400 列前序 | 通过 | `test_skip_to_later_node_rejected` |
| US1-AS3 按序推进 6 次全 200 | 通过 | HTTP 025-US2-AS5 空集逐节点全 200 |
| US1-AS4 failed 前序阻断后序；改回 todo 200 | 通过 | `test_failed_predecessor_blocks_forward_and_rework_unblocks`；HTTP US4-AS5 |
| US1-AS5 返工 doing 后可推进 | 通过 | 同上；HTTP US4-AS5（failed→doing→done→200） |
| US1-AS6 全 done 后改节点 failed → 200 且下游不回退 | 通过 | `test_no_auto_rollback_of_downstream`；HTTP 025-US1-AS5/AS6 |
| US2-AS1 规格 pending 置开发验收 → 400 指名规格 | 通过 | HTTP US4-AS4；`test_dev_accept_requires_specs_accepted` |
| US2-AS2 有 todo run 置测试 → 400；执行后 200 | 通过 | HTTP US4-AS2；`test_test_requires_all_runs_done` |
| US2-AS3 缺陷 fixing 置测试验收 → 400 指名缺陷 | 通过 | HTTP US4-AS3；`test_test_accept_requires_bug_clear` |
| US2-AS4 变更 doing 置测试验收 → 400；passed 后 200 | 通过 | HTTP US4-AS3/AS3+；`test_test_accept_requires_change_regressed` |
| US2-AS5 空集逐节点放行 | 通过 | HTTP 025-US2-AS5；`test_empty_set_gates_pass_on_new_version` |
| US3-AS1 六节点全 done → stage_done/gate 真 | 通过 | HTTP US4-AS6；`test_gate_computed_true_when_all_six_done` |
| US3-AS2 已 done 后改说明不重复验闸门 | 通过 | HTTP 025-US3-AS2（gate 仍真） |
| US3-AS3 退回 doing → stage_done/gate 假 | 通过 | HTTP 025-US3-AS3；`test_gate_turns_false_after_node_rollback` |
| US4-AS1 普通表单 enum 不套校验 | 通过 | `test_non_version_table_with_one_stage_enum_untouched` |
| US4-AS2 非惯例字段 id 按名称解析串行 | 通过 | `test_stage_nodes_resolved_by_name_when_ids_unconventional` |
| US4-AS3 首节点无前序 | 通过 | HTTP 025-US2-AS5 第一步 200；`test_serial_forward_allowed_in_order` |

## 十、与 board@4.yaml 的偏差（按严重度）

| 编号 | 严重度 | 偏差 | 影响 | 建议 |
|---|---|---|---|---|
| D-01 | **中（已修复）** | 六个技能原不接受 `--apply`；t11 在 `_tf_common.base_parser` 增加 `--apply`（`--dry-run` 优先），六入口同步暴露，SKILL/024 spec 补说明 | t9 时 024 的 9 条 AS 字面命令无法执行；**复评已按字面命令全部通过** | 已修复，见第十四节；无残留 |
| D-02 | **中低（已修复）** | t12 把 relation 分支提前到空值回退之前：空数组渲染「0 项」按钮；弹层空态直接显示「关联条目 · 0 项」+「暂无关联条目」，不请求目标表 | t9 时 021 US2-AS5 未通过；**复评已通过**，非空三列不变 | 已修复，见第十四节；无残留 |
| D-03 | 低 | 部分 AS 证据强度受限：代码走查（021 US1-AS3/US2-AS7/US3-AS1、022 US2-AS7/US4-AS4、024 US4-AS3/US5-AS2）；未逐一 reload（022 US4-AS2）；未逐一测量四角色五令牌（022 US3-AS5，3/4 实测） | 证据强度弱于运行态 | 后续补运行态用例；不影响本轮通过判定 |
| D-04 | 低（既有数据） | 线上 `bug` 表 `严重度`/`来源` 为 required，契约未标必填；门禁不比 `constraints` | 写缺陷必须带这两字段；契约与数据不一致 | 另立需求统一；门禁可选补 required 比对 |
| D-05 | 低（既有数据） | 6/8 项目 `indep` 行 id 不是 `NNN-AR`（demo-bench `S1…`、demo-cnc `UD-01-AR…`、demo `UD-04-AR`、demo-im `001-document-intake…`、demo-cloud `C-501…`、demo-edge `E-313…`） | case.id 前缀来自规格目录、`case.indep` 才指 indep；跨项目派生必须项目级映射，不能从 indep.id 推导；本轮只派生 tableflow，不构成缺陷 | 改项目级映射或 indep 加「用例前缀」列（不进本轮验收） |

## 十一、部署后需复验（线上 0.6.5 → v0.7.0）

线上仍是 `tableflow:0.6.5` 旧镜像：API 不返回 `kind`，门禁对线上实库报 48 条「表级 kind 缺失」（`us6/gate-live-oldapi.json`），**按基准不计缺陷**。部署 v0.7.0 后必须重跑：

1. **US1-AS3**：`GET /api/projects/{pid}/tables` 返回 `kind`（run=detail）；前端导航无「用例执行情况」；`GET /api/tables/<run>/rows/<id>` 200。
2. **020 拒绝路径**：`state=todo`+`result` → 400；重复纳入 → 400；两步写入第二步失败后第一步可回读。
3. **门禁对线上实库 0 差异**：`python3 backend/scripts/check_board.py --contract specs/019-test-contract/board@4.yaml --base http://<线上> --json`（期望 exit 0；当前旧 API 48 条 kind 属旧镜像假缺失）。
4. **stage_done/gate 落库**：线上 ver 行 `六节点是否全部完成`/`发布条件` 规则与值（当前库已 26 字段，部署后读接口应返回 kind 与计算值）。
5. **写后回读**：任一写接口 200 后立即 GET，值一致且响应 `no-store`。

验证覆盖范围：024 的 `tf-test-plan` 派生/幂等只在 **tableflow 一个项目**验证；其余 7 个项目未覆盖，不得据此推断跨项目可用（indep id 漂移见 D-05）。

## 十二、已知边界（不计缺陷）

**N1（t7 报备）**：六节点闸门只在节点**到达 done 那一刻**校验；之后证据恶化不会自动把 `gate` 转假。实测：`v9.9.4` 六节点全 done、gate=true；随后把未关闭缺陷 `BUG-RV-N1` 挂进 `ver.bugs`，`发布条件` 仍为 **true**（未触发重算/回退）。
语义边界：`发布条件=是` 表示「六节点均曾按当时证据通过」，**不表示当前证据仍全绿**；发布前需另行核对缺陷/变更集合。该行为与 025 契约「闸门只在到达 done 时校验、不自动回退下游」一致，故记为已知边界而非缺陷。

另：022 US4-AS4（localStorage 禁用）与 021 US1-AS3 等以代码走查通过，属证据强度限制（D-03）。

## 十三、结论中的依赖

- 019 US4-AS6 曾依赖 023；023 已终态（`specs/023-cell-compute/spec.md`，T2 completed），本轮 stage_done/gate 用真实六节点表达式实测通过，**该依赖已关闭**。
- 019 与 020 的重叠：019 US3-AS4/AS6 判「规则被定义且被拒绝」，020 判「拒绝路径与错误码」；本轮未重复计分、未判越界。
- 022 角色矩阵按 t10 后映射判：软件测试 = ver/case/dep/bug（4 页签）；系统工程 3、软件开发 4、全局 5。

## 十四、复评记录（t13，2026-11-22 18:45）

**触发**：t11（D-01 六个技能补 `--apply`）、t12（D-02 空关联可点）、t10 完成；t13 只重跑受影响的 10 条 AS + 回归，其余 140 条**基于 t9 结论沿用、本次未重验**。

### 14.1 两次评审差异

| 项 | t9 初审（18:18） | t13 复评（18:45） |
|---|---|---|
| 021 US2-AS5 空 runs 弹层 | 未通过（无按钮） | **通过**：单元格按钮「0 项」，弹层「关联条目 · 0 项」+「暂无关联条目」 |
| 024 `--apply` 9 条 AS | 未通过（argparse exit 2） | **通过**：按 spec 字面命令复跑，9/9 断言通过 |
| 通过/未通过 | 140 / 10 | **150 / 0** |
| 待部署复验 | 5 项 | 5 项（未变） |
| 已知边界 | N1（未变） | N1（未变） |

### 14.2 D-01 复评证据（024 的 9 条，按 spec 字面命令）

- 独立执行 t11 回放脚本 `bash specs/024-role-skills/verify/run_d01_apply.sh` → **exit 0**，`rerun/d01-rerun.log`；`rerun/d01-results.json` 的 `checks`：`nine_as_assert_ok=true`、`six_skills_accept_apply=true`、`no_exit_2=true`、`no_unrecognized_arguments=true`、`dry_run_priority_readonly=true`。
- 逐条（results.json `steps`）：US3-AS1 27 case/27 run；US3-AS2 created 0/0、updated 1；US3-AS3 orphans=`019-US9-AS1` 且未删；US3-AS4 27 run 全 todo、`ver.runs=27`、无计划表；US3-AS5 exit 1 前序未 done、writes=0；US4-AS1 exit 1 列未完成任务、writes=0；US4-AS2 dev/implement 读回 done；US4-AS3 exit 1 列 pending 规格、零写；US4-AS4 dev_accept=done。
- 独立旁证（另一份夹具库、字面 `--apply`）：`v9.9.0 --apply` → failed/exit 1/writes 0（前序未 done）；`v9.9.1 --apply` → success、created 0/0、reused 2；`--apply --dry-run` → `mode=dry-run`、`apply=true`、`apply_ignored_by=dry-run`、writes 全 skipped。证据 `rerun/d01-independent-*.json`。
- 六技能 `--help` 均含 `--apply`；未识别参数退出码 0 例。

### 14.3 D-02 复评证据（021 US2-AS5）

- 本地新代码 + 快照副本：v9.9.4（空 runs）单元格渲染 `<button class="relation-link" title="关联条目 · 0 项" aria-label="关联条目 · 0 项">0 项</button>`；点击弹出「关联条目 · 0 项」+「暂无关联条目」，无表格、无 loading、无报错。证据 `rerun/ui-d02.json`、`rerun/d02-empty-modal.png`。
- 非空回归：v9.9.9 弹层仍为「关联条目 · 10 项」三列（编号/用例号/执行状态），首行 `v9.9.9--019-US1-AS1 / 019-US1-AS1 / 已执行`；`rerun/d02-nonempty-modal.png`。
- `npm run build` exit 0（`rerun/build.log`）。

### 14.4 回归（确认无回退）

| 项 | 结果 | 证据 |
|---|---|---|
| `cd backend && .venv/bin/python -m pytest -q` | **201 passed, 1 warning in 7.36s** | `rerun/pytest.log` |
| 门禁 `--template`（board@4） | **exit 0，0 差异** | `rerun/gate-template.json` |
| 门禁本地新代码（干净迁移后快照副本） | **exit 0，0 差异** | `rerun/gate-local-clean.json` |
| 门禁本地（评审写入过的副本） | exit 1 / 8 条——**均为评审夹具污染**（`p-detailonly` 章节项目、`rv-ok*` 临时计算字段），非产品回退 | `rerun/gate-local.json` |

### 14.5 复评后仍保留的结论

- **待部署复验 5 项**（第八节）不变：线上 0.6.5 的 48 条 kind 缺失仍按基准不计缺陷。
- **已知边界 N1** 不变：闸门只在到达 done 时校验，之后证据恶化不自动转假；「发布条件=是」= 曾按当时证据通过。
- **已知数据偏差**不变：6/8 项目 indep 行 id 非 `NNN-AR`，跨项目派生必须项目级映射；024 的 tf-test-plan 仅覆盖 tableflow。
- t9 初审的全部证据目录（`.tmp-shots/review-v070/`）保持原样，未被覆盖。
