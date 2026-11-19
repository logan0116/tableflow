---
name: ms-update
description: "按版本把specs的验收场景同步成MeterSphere功能用例并建/复用测试计划：写前查重、写后GET读回核对，用例名保留场景号。触发词：MS同步、建用例、测试计划、ms_update、MeterSphere用例、版本用例。"
---

# ms-update：spec场景 → MS用例与测试计划

**一句话**：`specs/<feature>/spec.md`是唯一真源，MeterSphere是派生——一个验收场景一条用例，
名字带`<规格号>-US<故事号>-AS<场景号>`；写前查重、写后读回，计划能建就建、能复用就复用，
**关联不假装成功**（本版本没有关联写入API，见第7节）。

## 运行环境（脚本解释器）

脚本依赖`cryptography`，用**系统`python3`**运行（如`/usr/bin/python3`）；
`backend/.venv/bin/python`没有该依赖，会报`ModuleNotFoundError: No module named 'cryptography'`。
下文所有`python3 ...`命令均指系统解释器。

## 何时用

- 一个版本开工，要把`specs/`里若干份spec的验收场景落成MS功能用例
- spec改过，要把改动同步回MS（同名场景就地更新，不新增重复用例）
- 要建/复用本版本的测试计划，并确认平台上到底挂了几条用例

**不做什么**：不改`specs/`下任何文件；不写执行结果（那是`ms-implement`的活）；
不改`board@1`口径（那是`specs/008-board-contract/board@1.yaml`）；不删除他人用例。

## 连接与凭据纪律

```bash
export MS_TOOLS_DIR=~/PycharmProjects/cnc_nexus/tools/metersphere   # ms_env.py 所在目录
```

- 客户端统一走项目里的`ms_env`（`from ms_env import ms_client, ids`），凭据在`ms_creds.env`；
- **绝不打印AK/SK**，也不把`ms_creds.env`复制进本仓库、贴进聊天记录、放进skill包；
- 请求只能发往凭据文件声明的host（`ms_env._guard_host`会拦），换实例要改凭据文件而不是改脚本。

实测实例：`http://192.168.1.155:8081`（MeterSphere CE v3.6.9-lts），组织100001；
`projectId/templateId/priorityFieldId`从`ms_env.ids()`取，可用`--ms-project`覆盖。

**多产品**：MS项目按 `--ms-project` > `$MS_PROJECTS_FILE`/仓库根`.ms-projects.json`/`~/.config/ms/projects.json` > `ms_env` 默认解析；
模块与计划名按 `--project`/`--version` 生成，不再写死 `tableflow v0.6.0`：

```bash
python3 assets/ms_sync.py --project fd_system --version v7.0.2 --apply   # 生成 "TF · fd_system v7.0.2" 与 "fd_system v7.0.2 · 契约与技能验收"
```

## 落点与命名（以下为 v0.6.0 的实例，实际按参数生成）

| 对象 | 名称 | id（2026-11-19实测） |
|---|---|---|
| 功能用例模块 | `TF · tableflow v0.6.0` | `1744872795197685760` |
| 测试计划模块 | `TF · tableflow` | `1744872966996377600` |
| 测试计划 | `tableflow v0.6.0 · 契约与技能验收` | `1744872984176246784` |

- 用例名：`<008>-US<1>-AS<2> <Then摘要>`，例如`008-US1-AS1 得到ver16字段、indep16字段、dep9字段`；
  **场景号必须保留**——它是查重键、执行定位键、缺陷回溯键；
- 前置条件写`【前置条件】Given`、`【来源】specs/<dir>/spec.md#USn-ASm`、`【环境】`三段，
  来源行必须能点回spec原文；
- 步骤一条：`desc=When`、`result=预期：Then`；`caseEditType=STEP`，`steps`传**JSON字符串**。

## 流程（五步，缺一步不算完成）

```bash
# 1) 预览：解析spec、列出将要新建/更新的用例（不写平台）
python3 skills/ms-update/assets/ms_sync.py

# 2) 写入：建模块（不存在时）→ 逐条 add/update → GET detail 读回核对 → 建/复用计划
python3 skills/ms-update/assets/ms_sync.py --apply

# 3) 只做其中几份spec
python3 skills/ms-update/assets/ms_sync.py --specs 008 010 --apply

# 4) 只读体检：模块内用例、计划内关联条数、关联端点探测结果
python3 skills/ms-update/assets/ms_sync.py --report
```

1. **解析**：正则抓`### User Story N - 标题 (Priority: Pn)`与`**Acceptance Scenarios**`下的
   `1. **Given** … **When** … **Then** …`；一份spec的场景数应与spec里条数一致（v0.6.0：008=10、009=21、010=14、015=20）。
2. **查重**：按`<规格号>-US-AS`前缀在**本模块内**匹配（MS不落`refId`，名称前缀才是稳定幂等键；
   场景号跨spec会撞，必须限定模块）。
3. **写**：命中就full-update（先GET detail拿全字段，剥只读字段，再整份提交）；没命中就add，再补一次
   update让优先级`customFields`落库（add不落`caseId`绑定）。
4. **读回**：`GET /functional/case/detail/{id}`核对名称/模块/前置条件/步骤+预期四项，任一不符即failed；
   **不信200、不信返回里的id**。
5. **计划**：同名计划存在就复用，不存在则建计划模块+计划；建成后读回`计划内关联用例数`。

## 平台契约要点（实测，别猜）

| 操作 | 端点 | 必填与坑 |
|---|---|---|
| 用例分页 | POST `/functional/case/page` | `pageSize ≥ 5`，翻页到`total` |
| 建用例 | POST(multipart) `/functional/case/add` | `projectId/templateId/moduleId/name/caseEditType`；JSON直传报500 |
| 改用例 | POST(multipart) `/functional/case/update` | **全量覆盖**：不带`steps`会把步骤清空 |
| 用例详情 | GET `/functional/case/detail/{id}` | 读回核对只认这个 |
| 用例模块树 | GET `/functional/case/module/tree/{pid}` | 扁平列表，首个是虚拟`root`（不能挂用例） |
| 建用例模块 | POST `/functional/case/module/add` | `{projectId, name, parentId:"NONE"}` |
| 计划分页 | POST `/test-plan/page` | **必带`type:"ALL"`** |
| 建计划 | POST `/test-plan/add` | `{projectId, moduleId, name, type:"TEST_PLAN", description, groups:[], testPlanning:null}`；`type`写`ALL`会让计划打不开 |
| 计划模块树 | GET `/test-plan/module/tree/{pid}` | 新项目只有虚拟`root`，建计划前必须先建真实模块 |
| 计划内用例 | POST `/test-plan/functional/case/page` | `{testPlanId}`；返回行里`id`是**关联行id**、`caseId`是用例id |

`templateId`取项目内任一条已有用例的`detail.templateId`（列表响应里没有这个键）。

## 三态与失败处理

写接口统一按响应体判终态，不看HTTP码：

- `success`（`{"result":...}`或`code:100200`）→ 仍要读回；读回不符**改判failed**；
- `failed`（400/100400）→ 原样报错，**不重试**（重试只会得到同一个400）；
- `unknown`（503/100500）→ 先GET读回，再决定success/failed，**不得直接当成功**。

汇总必须写清：`新建N｜更新N｜跳过N｜失败N｜读回核对通过X/总`。有失败就退出码非0。

## 已知缺口：计划↔用例关联没有API（未验证范围）

v3.6.9-lts实测：**没有关联写入端点**。探测清单（`probe_association()`逐个打）覆盖
`/test-plan/functional/case/batch/add/0`、`batch/relate/0`、`relate`、`add`、`association/0`、
`/test-plan/association/{id}/case`、`/test-plan/case/add`等**18个候选路径，全部返回
500 `No static resource`**（即路径不存在；天真的404不是判据，Spring静态资源兜底是假500）。
前端产物里也搜不到对应写路径，只有读侧的`/test-plan/association/page`。

因此：**新建计划关联用例数为0是预期结果，不是脚本失败**。要让计划真正带上用例，二选一：

1. 人工在MS界面「计划详情 → 功能用例 → 关联用例」勾选（推荐，一次几十条手点可忍）；
2. 按`08-MS操控手册.md`第五节直写`test_plan_functional_case`（需SSH到155与MySQL，红线：备份+幂等+读回；本skill内不做）。

**未验证范围（必须如实写进报告）**：计划创建已验证；计划与用例的关联**未**通过任何通道完成，
关联条数0；因此`ms-implement`的结果回写在本轮无法端到端跑通（见`skills/ms-implement/SKILL.md`第6节）。

## 报告格式（给用户/队长的六字段）

1. 版本与spec范围；2. 解析出的场景数与各类计数；3. 写入结果（新建/更新/跳过/失败）；
4. 读回核对通过率与不符项；5. 计划id与关联条数（含"关联无API"的结论）；
6. 未验证范围与下一步（界面关联→跑`ms-implement`）。

## 自检清单

- [ ] `--report`里模块用例数 = spec场景总数（v0.6.0为65）
- [ ] 每条用例名以`NNN-USn-ASm`开头
- [ ] `detail`读回的`steps`非空且每条`desc/result`都有
- [ ] 计划`type`是`TEST_PLAN`，能在界面打开
- [ ] 报告里写了"关联未完成"，没有把0条关联说成"已挂载"
