# v0.6.0复验报告（t18，2026-11-19）

复验人：qa。窗口：12:49–12:55。范围：v0.6.0（008/009/010/015）与第一轮8条缺陷的回归确认；只读，不改源码、不写看板业务行、不执行git写操作。
证据目录：`.tmp-shots/qa-v060b/`（脚本与日志可逐条重跑；沿用`.tmp-shots/qa-v060/`、`.tmp-shots/qa-v061/`的脚本）。

## 一、结论

**可发布。**

依据（五条，均可复现）：
1. 8条缺陷**全部关闭**（V060-01…08逐条见第三节），无“部分关闭”或“未关闭”。
2. 后端`pytest -q` **123 passed**，全绿；010的空集/悬空/禁覆盖/重算四种情形各独立复现通过。
3. tf-update 四条拒绝路径（无版本/不存在/非planned/不晚于已发布）在真实看板各跑一次，均`failed`且**零写入**（`tf-indep`仍15行、`tf-ver`仍10行、`099-AR`不存在）。
4. ft-status 在四表项目`tableflow`与三表项目`fd_system`各跑一次：四表按bug表算闸门；三表输出“无法完整判定/Bug闸门未启用”，**未迁移不降级**、不报错、不把缺表当0。
5. 契约（board@1 rev3、board@2 rev2）与看板skill三处旧表述 grep **命中0**，skill覆盖board@2全部53个字段名。

**与发布相关的唯一待办（不阻塞发布）**：线上服务仍为旧代码（010/013未部署），因此“闸门禁覆盖”在线上尚未生效；发布部署后需跑一次`--probe-override`确认。本文不据此判“已生效”，也不因此判“不可发布”。

## 二、验证基线

| 项 | 值 |
|---|---|
| `specs/008-board-contract/board@1.yaml`（rev3） | `142ccf067ab372858a2cb898e78506f7a6dcc8adeb86a1e16210d6d507930537` |
| `specs/011-bug-table/board@2.yaml`（rev2） | `d45d159f149497e3269ee4d5445e11fef808ba3683c66b99b4688fa9b4b088a1` |
| `backend/src/tableflow/calculation.py` | `f22191bdb0f71e8f2fdc75496dc57db29c29c11adfc47e72d110c766306ec5b9` |
| `backend/src/tableflow/write_service.py` | `39b0b1029ae85d2a4b002fa8b99529107fd2e7ed18d3fdda00f087fff498bc7e` |
| `skills/tableflow-board/SKILL.md` | `40d8dac50270e45cc7409a679ce93eb7e59403ecef91f62f035cac3d97782175` |
| `skills/tf-update/SKILL.md` | `4b98f11f0cf226ae5d3443c9643738d272773b488609f099957e8072d71cdbef` |
| `skills/ft-status/SKILL.md` | `1d1a6b947db38e5c3bce534f13e1a021cada67ce49aec00e34907b3be85440c1` |
| 后端回归 | `123 passed, 1 warning in 4.53s`（`pytest.log`） |
| 线上看板 | `http://192.168.1.155:8090`（只读GET；服务端仍旧代码） |

## 三、8条缺陷逐条结论

| 缺陷 | 结论 | 证据（命令/输出/行号） |
|---|---|---|
| V060-01 契约与skill口径冲突 | **已关闭** | `grep -n "没有第四张表\|开发进度\|测试进度\|未清Bug数\|Bug已清空\|回归通过\|文档状态\|其余阶段用text或enum" board@1.yaml board@2.yaml skills/tableflow-board/SKILL.md` → 三文件命中数均**0**；skill对board@2`53/53`字段名全覆盖；`specs/008-board-contract/conflicts-t007.md`记录16条冲突+改写 |
| V060-02 挂版本规则 | **已关闭** | 四条拒绝实测：无version→`failed`+提问（列出planned v0.2.0/v0.6.0/v0.6.1/v0.6.2）；`v0.2.0`→“不晚于最近已发布版本v0.5.1，拒绝登记”；`v0.5.1`→“发布状态是released，只能挂到planned版本”；`v9.9.9`→“目标版本不存在”。复验后`tf-indep`15行、`tf-ver`10行不变，`099-AR`不存在。线上`v0.2.0`保持planned是队长决定，不计入缺陷 |
| V060-03 闸门标记 | **已关闭**（线上生效待部署） | 契约`conventions.gate_mapping`在两份契约逐字一致（board@1/board@2）；`migrations.gate-tag-existing` status=“已执行（2026-11-19）：7个项目…”，`executed_fields`7项；线上7项目`发布条件`字段`options.gate=true`（`live_gate_tags.log`）；仓库`tests/test_computation_010.py`gate用例随pytest通过。线上服务旧代码，禁覆盖未生效，部署后以`--probe-override`复核 |
| V060-04 悬空后行不可编辑 | **已关闭** | `verify_repair_v060.log`：删被引用行后改无关字段`200`（修前400）、显式提交悬空id`400 关联目标行不存在`、清空关联`200`、缺必填`400`、超max`400`；`tests/test_repair_v060.py`3例通过 |
| V060-05 契约未声明行id | **已关闭** | board@1`row_id`={ver.version,spec.id,change.id}；board@2增加`bug.id`（`check_contracts.log`） |
| V060-06 状态跨域同名歧义 | **已关闭** | 两份契约`conventions.status_values_scope`逐字一致：“同域互斥、跨域允许字面同名、引用必须带域前缀、判定只看本域字段” |
| V060-07 sum空集浮点 | **已关闭** | `rules.empty_set_numbers`声明`count=0(整数)、sum=0.0(浮点)、percent=null、rollup空集语义`；`verify_010.log`落库`'0'/'0.0'/'true'/null`，与契约一致 |
| V060-08 010 SC-003证据不足 | **已关闭** | `specs/010-computation/spec.md`131行“SC-003的核验方法与基线（V060-08补强）”，155行给出基线7项目22表192行、sha256`b4e353c5…`；`.tmp-shots/repair-v060/baseline-2026-11-19.json`存在（7项目） |

## 四、复验实测明细

| 项 | 结果 | 证据 |
|---|---|---|
| 后端`pytest -q` | `123 passed` | `pytest.log` |
| 010空集 | `count=0`、`sum=0.0`、`rollup all=true`、`percent=null`；落库`'0'/'0.0'/'true'/null` | `verify_010.log` US1段 |
| 010悬空 | 删不达标行后`rollup all=false`且`and闸门=false`；摘掉失效id后恢复`true`；`count=2`、`percent=100.0` | `verify_010.log` US2段 |
| 010禁覆盖 | `gate=true`字段覆盖→`400 闸门字段「c-gate2」禁止人工覆盖`，覆盖值`None`；数量类打标`400`；非闸门布尔字段仍可覆盖；历史覆盖可清除 | `verify_010.log` US3段 |
| 010重算 | 改源行/新增行/删源行后读接口同事务更新（`count`2→3→2，`all`随状态变化） | `verify_010.log` US4段 |
| tf-update 拒绝路径1 无版本 | `failed`“未指定目标版本，拒绝登记（不自动选择版本）”，附一条提问 | `tf_reject_paths.log` |
| tf-update 拒绝路径2 不存在 | `failed`“目标版本 v9.9.9 不存在” | 同上 |
| tf-update 拒绝路径3 非planned | `failed`“目标版本 v0.5.1 的发布状态是 released，只能挂到 planned 版本” | 同上 |
| tf-update 拒绝路径4 不晚于已发布 | `failed`“目标版本 v0.2.0 不晚于最近已发布版本 v0.5.1，拒绝登记” | 同上 |
| tf-update 零写入 | 复验后`tf-indep`15行、`tf-ver`10行、`099-AR`404 | 同次脚本尾部核对 |
| ft-status tableflow（四表） | 顶部结论“不可发布”，三项就绪逐条：独立需求否（4行未accepted）、依赖空集真、上一版本v0.5.1无缺陷真 | `ft_tableflow_v060.log` |
| ft-status fd_system（三表） | “**无法完整判定**：该表未迁移到board@2（项目只有三张表，缺「缺陷」表），Bug闸门按未启用处理”；两项就绪给出结论，未把缺表当0、未报错 | `ft_fdsystem_702.log` |
| 009分类判定（只读演练） | 四分支各给唯一结论：`change`（007-AR#US2-AS1）、`in_place`（010-AR#US1-AS3）、`out_of_board`（部署脚本）、`new_spec`（CSV导出，且`grep`命中1行为词形重合）；未执行写步骤 | `classification_drill.md` |

## 五、验收建议（逐条）

| 需求 | 建议 | 依据与备注 |
|---|---|---|
| 008契约board@1 | **可置 accepted** | FR-001…009全部满足；FR-010从“不通过”转为满足（skill零旧表述、53/53字段覆盖）；US3-AS4（判据追问）属009执行面，已在`classification_drill.md`以四分支只读演练覆盖 |
| 009 tf_update | **可置 accepted**（附说明） | 四条版本拒绝+登记器+幂等+冲突+清理实测；分类四分支演练通过。备注：`unknown`三态未实测（线上无503注入手段），建议在验收记录注明“人工路径未覆盖”，不作为驳回理由 |
| 010计算口径 | **可置 accepted** | 四情形独立复现通过；`pytest`123 passed；SC-003方法与基线已补 |
| 015 ft_status | **可置 accepted** | 四表/三表两形态实测；“未迁移不降级”符合011过渡期要求；全程只读 |

一句话：**008/009/010/015 四条均可置`验收状态=accepted`**；建议同批置位，避免`独立需求就绪`因个别行pending而长期为否。

## 六、未验证与风险（不影响“可发布”结论）

| 项 | 状态 | 说明 |
|---|---|---|
| 线上闸门禁覆盖 | 未生效 | 线上服务仍旧代码；010部署后跑`--probe-override`复核（仓库用例已通过） |
| 009 `unknown`三态 | 未实测 | 无503注入手段；skill已按“回读判定、不得当成功”写明 |
| 009 分类为人工判定 | 已演练未自动化 | 只读演练覆盖四分支；技能本身是给Agent的流程，非脚本可断言 |
| 011/014/012/013 | 不在本任务 | 011/014属v0.6.1（t10已验）；012/013属t12 |

## 七、证据清单（`.tmp-shots/qa-v060b/`）

| 文件 | 内容 |
|---|---|
| `pytest.log` | 123 passed |
| `check_contracts.py`/`check_contracts.log` | 两契约结构、row_id、gate_mapping、status_values_scope、empty_set_numbers、migrations |
| `live_gate_tags.log` | 线上7项目`发布条件`gate:true |
| `verify_010.log` | 010四情形独立复现 |
| `verify_repair_v060.log` | V060-04修复复现（400→200等五项） |
| `tf_update_runner.py` | tf-update登记器（从SKILL.md抽脚本） |
| `ft_tableflow_v060.log`/`ft_fdsystem_702.log` | 015两形态实测 |
| `classification_drill.md` | 009分类四分支只读演练 |
