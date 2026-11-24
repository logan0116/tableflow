# v0.8.3 缺陷显现化

目标：让 `specs/verify-v080.md` 里 19 条问题**每条都有一条测试能自己抓出来**，而不是靠人工点。
本版不登记看板需求（用户 2026-11-24 决定），产物是测试与修复；发布仍按 v0.8.3 tag + 部署。

## 一、判据

1. 19 条缺陷各自至少 1 条用例，**修复前必然失败**（失败原因必须是缺陷本身，不是夹具缺字段、不是 404/500）。
2. 失败用例用 `xfail(strict=True)` 登记：只有真的失败才算登记成功；修复后 `xpass` 会变成硬失败，强制移除标记。
3. 收口条件：`0 xfailed`，全量套件绿，且每条缺陷的用例都在。
4. 技能 9 个入口各至少 1 条**端到端**用例：起真服务端 + subprocess 跑脚本（当前为零覆盖）。
5. 测试数据形态矩阵：版本行 id 至少覆盖 `v0.8.3`、`3.0.0_012`、`20261107-01-v1.1.132.13006` 三种形态。

## 二、三层测试体系

| 层 | 对象 | 手段 | 现状 |
|---|---|---|---|
| L1 引擎 | `backend/src/tableflow/*` | TestClient + seed 看板 | 已有 335 条，缺攻击面与数据形态 |
| L2 技能 | `skills/*/scripts/*.py` | 真 uvicorn + subprocess 跑入口 | **零覆盖**，本轮新建 |
| L3 契约 | `specs/019-test-contract/*.yaml`、`specs/*.md` | 解析契约文本断言实现一致 | 只有文档同步检查 |

L2 是本轮重点：19 条里 6 条在技能侧，之前的 11 个“技能测试”只 import 了两个纯函数，没执行过入口。

## 三、缺陷 → 用例清单

`已落地` = 已提交并验证为红；`待补` = 尚未写。

### 后端（L1）

| 编号 | 用例 | 断言 | 状态 |
|---|---|---|---|
| B1a | `test_b1_shrinking_run_list_must_not_close` | 同请求把 runs 缩减为只含 pass 再置 done → 400 | 已落地 |
| B1b | `test_b1_empty_run_list_must_not_close` | runs 置空再置 done → 400 | 已落地 |
| B2 | `test_b2_new_dep_row_must_pass_change_flow` | POST 新建 dep 直接 passed、无证据 → 400 | 已落地 |
| B3 | `test_b3_drop_must_refuse_released_version` | 已发布版本持有的需求 drop → 拒绝 | 已落地 |
| B4 | `test_b4_drop_must_be_atomic` | 注入末步失败后，版本关系不得改变 | 已落地 |
| B5 | `test_b5_drop_not_confused_by_other_project` | 另一项目同编号需求不影响本项目 drop | 已落地 |
| B6 | `test_b6_migration_reports_failure` | 建字段/扩枚举失败 → 非零退出且计数准确 | 已落地 |
| B7 | `test_b7_cleanup_needs_run_table` | 允许表只有 ver/indep 时 cleanup 仍可用 | 已落地 |

### 技能（L2）

| 编号 | 用例 | 断言 | 状态 |
|---|---|---|---|
| S1 | `test_s1_dev_plan_runs_on_real_spec` | 用 042 规格跑 `tf-dev-plan` 不崩 | 待补 |
| S2 | `test_s2_implement_keeps_plan_task_evidence` | 写 implement 证据后 plan/task 证据仍在 | 已落地 |
| S3 | `test_s3_skeleton_plan_is_not_done` | 只有骨架（「待补」）的 plan → 不得置 done | 已落地 |
| S4 | `test_s4_regression_only_version_proceeds` | 无独立需求、只有 runs 的版本能推进节点 | 已落地 |
| S4b | `test_s4_dep_only_version_proceeds` | 只有依赖需求的版本能推进开发节点 | 已落地 |
| S5 | `test_s5_apply_with_dry_run_writes_nothing` | `--apply --dry-run` 后库里零变化 | 待补 |
| S6 | `test_s6_non_semver_version_and_scenarios` | 非 semver 版本可跑；`**S1.1** **Given**` 能派生 | 已落地 |

### 契约（L3）

| 编号 | 用例 | 断言 | 状态 |
|---|---|---|---|
| C3 | `test_c3_board5_declares_dropped` | board@5 的验收枚举含 dropped | 已落地 |
| C4 | `test_c4_reconfirm_does_not_exempt_forever` | 宪法版本升级后，旧「已重新确认」不再豁免 | 已落地 |
| C6 | `test_c6_fr_under_requirements_section_counted` | FR 直接写在 `## Requirements` 下也要计数 | 已落地 |
| C5 | 映射重做（非单条用例） | 每场景 1 条独立断言，禁止共用；见第五节 | 已落地 |

## 四、执行顺序

1. P1 后端复现：B1、B2（已落地），补 B3–B7。
2. P2 技能基座：真服务端 + 脚本入口调用器；先复现 S1、S5（最容易，覆盖也最薄）。
3. P3 技能其余（S2、S3、S4、S6）与契约（C3、C4、C6）。
4. P4 修复到 `0 xfailed`，逐条删 `xfail` 标记。
5. P5 121 条映射重做。

修复不早于复现：每批先证明“测得出来”，再动代码。

## 五、映射重做规则

现行问题是“先有测试再凑场景”。重做规则：

1. 一个场景对应一条测试函数，测试名必须含场景号（`..._042_us1_as1_...`），便于反查。
2. 测试体内必须有一条断言对应场景的 `Then`，而不是“行存在”“字段非空”这类存在性断言。
3. 自检从“函数名存在”改为“场景号出现在函数名里 + 该函数至少一条断言”，并对 38 条共用映射人工复核。
4. 121 条重跑结论以新映射为准，旧结论作废。

## 六、不做什么

- 不登记看板需求，不建版本范围，不走六节点。
- 不为通过而放宽断言：修复期间允许红/`xfail`，不允许把 `400` 改成 `200` 的期望来凑绿。
- 不改 121 条历史结论的措辞去圆场，直接标注作废并重出。

## 七、一致性守卫（已落地，绿）

来自线上观察：v0.8.3 建了 19 条用例后，“测试”列仍显示 0/0、六灯全灰。

| 用例 | 断言 | 结果 |
|---|---|---|
| `test_ratio_refreshes_immediately_after_linking_runs` | 版本收录用例后，`用例完成/总数` 立刻反映（2/1），不需要手工 recompute | 绿 |
| `test_case_done_is_false_while_any_run_unexecuted` | 存在未执行用例时，`用例是否完成` 必须为否 | 绿 |
| `test_gate_stays_false_until_all_six_nodes_done` | 四灯 done + 一灯 doing + 一灯 todo → 发布条件为否；六灯全 done → 为是 | 绿 |

这三条是**防回退**，不是缺陷凸显：本地按线上同样顺序（先建版本、再建执行记录、最后关联用例）复现时，
引擎的 `PATCH` 之后立即得到 `total=2 / done=1`，计算是即时的。

### 未定性的观察

线上 v0.8.3 当时读到 0/0，调用 `POST /api/agent/tables/tf-run/recompute` 后恢复为 12/19。
本地同序复现得不到 0/0，因此**不能判定为引擎重算缺陷**。待查方向：部署侧是否多进程、
读连接是否持有旧快照、以及脚本批量写入与该次读取的时序。在复现出稳定条件之前不入缺陷台账。

### 六灯不自动推导

六节点是普通写入字段，不是计算字段：建了用例和执行记录不会点亮灯。本轮按实际工作逐灯写入
（版本需求设计/测试设计/开发/开发验收 = done，测试 = doing，测试验收 = todo），发布条件保持否。
纯回归版本因为没有开发动作，会卡在串行的第 3、4 灯——与 S4/S4b 是同一口径问题。
| S7 | P1 | 测试验收判定不通过时只抛错退出，节点停在 todo，无法区分「没做」与「没过」 | `tf_test_check.py:170` | 复现 | `if blockers: raise SkillFailure(...)` 之后没有写 `failed`；四态里 failed 才是「做过且未通过」，036 也按 failed 记录不放行 |
