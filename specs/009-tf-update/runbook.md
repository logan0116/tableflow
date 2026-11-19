# tf_update实跑记录（真实看板）

**时点**: 2026-11-19 12:23（Asia/Shanghai）

**实例**: `http://192.168.1.155:8090`，项目`tableflow`

**身份**: `X-Agent-Id: agent-tf-ftskills` + `X-Origin: human-request`

**交付物**: `skills/tf-update/SKILL.md`；本条记录里的每条命令都能原样重跑。

**版本规则提示**: 第2-9节是V060-02修复前（自动取最早planned）的历史记录；修复后规则="目标版本必须由人给出"，复验见第10节。

**结论**: 分类给出唯一结论与依据；登记成功并挂到显式指定的演练版本（当时规则是"最早planned"，V060-02后已改为必须显式指定版本）；同参数重跑幂等；同id换条款报冲突不覆盖；演练行与临时版本已删除，`v0.6.0`逐字段与演练前相同，`tf-indep`回到15行、`tf-ver`回到10行。

---

## 0. 执行前快照

```bash
curl -s $TF_BASE/api/tables/tf-ver/rows/v0.6.0 \
  | python3 -c "import json,sys;print(json.dumps(json.load(sys.stdin)['row']['values'],ensure_ascii=False))"
curl -s $TF_BASE/api/tables/tf-indep/table | python3 -c "import json,sys;print('tf-indep',len(json.load(sys.stdin)['rows']))"
curl -s $TF_BASE/api/tables/tf-ver/table  | python3 -c "import json,sys;d=json.load(sys.stdin);print('tf-ver',len(d['rows']))"
```

```
tf-indep 15
tf-ver 10
```

`v0.6.0`关联`["008-AR","009-AR","010-AR","015-AR"]`，`开发进度=75`、`场景总数=65`、`任务总数=52`（009/015的场景数与任务数由本任务登记，见末尾）。

## 1. 分类（只读）

### 1.1场景索引（证据的取值范围）

```bash
python3 - <<'PY'
import glob, re
for path in sorted(glob.glob("specs/*/spec.md")):
    text = open(path, encoding="utf-8").read()
    stories = re.split(r"^### User Story ", text, flags=re.M)[1:]
    total = 0
    for index, block in enumerate(stories, 1):
        title = block.splitlines()[0].split("(Priority")[0].strip()
        scenes = len(re.findall(r"^\d+\. \*\*Given\*\*", block, flags=re.M))
        total += scenes
        print(f"{path}  US{index}  AS{scenes}  {title}")
    print(f"{path}  合计 US{len(stories)} AS{total}")
PY
```

输出（节选，全量见上一条命令）：

```
specs/007-ui-nav-refresh/spec.md  US2  AS5  2 - 全局刷新按钮
specs/007-ui-nav-refresh/spec.md  合计 US2 AS10
specs/008-board-contract/spec.md  合计 US3 AS10
```

`008-AR`的`合计 AS10`与看板`008-AR`的场景数10一致，说明"场景数 = `**Acceptance Scenarios**`条目数"的口径成立。

### 1.2覆盖检索

```bash
grep -rniE "导出|CSV|excel" specs/*/spec.md
```

```
specs/005-ui-visual/spec.md:146:- **列宽估算（ColumnWidthEstimate）**：由字段 `type`、`name`、是否首列推导出的像素宽度，只在字段集合变化时重算。
```

命中项是"推导出的像素宽度"里的词形重合，不是导出能力。**关键词命中只是线索，必须读原文。**

### 1.3分类结论

| 项 | 值 |
|---|---|
| 需求 | 看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称 |
| 结论 | `new_spec`（判定树第3分支：现有规格都不覆盖） |
| 依据 | `新增条款`；已比对001-008，无导出/CSV相关条款与场景 |
| 动作 | `indep`新增一行（演练号段`099-AR`） |

反例对照（`change`分支怎么给依据）：若需求是"刷新后还要保留滚动位置"，它改的是已`accepted`的007-AR的验收口径，依据应写`007-AR#US2-AS2`（该场景只承诺保留项目/表格/筛选），落到`dep`开单。

## 2. 建演练版本（让"最早planned"规则被真实走到）

```bash
H=(-s -H "X-Agent-Id: $TF_AGENT" -H 'Content-Type: application/json' -H 'X-Origin: human-request')
curl "${H[@]}" -X POST $TF_BASE/api/agent/tables/tf-ver/rows/v0.0.1-test \
  -d '{"values":{"tf-v-ver":"v0.0.1-test","tf-v-status":"planned","tf-v-date":"2026-01-01T00:00:00+08:00",
       "tf-v-bug-open":0,"tf-v-indep":[],"tf-v-dep":[],
       "tf-v-note":"tf-update 演练用临时版本，演练结束即删除"}}'
```

```
{"result":"success","id":"v0.0.1-test"}
```

正式版本都没有`发布时间`，该演练版本日期为2026-01-01，按"日期升序、空日期最后"规则它成为最早的`planned`。

## 3. 登记（脚本从SKILL.md原样抽取执行）

```bash
export TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。","dir":""}'
awk '/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}' skills/tf-update/SKILL.md | bash
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "clause": "看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。",
 "steps": [
  "写行：success (http 200)",
  "挂版本：v0.0.1-test success (http 200)",
  "回读：四项一致"
 ],
 "write": {"http": 200, "result": "success", "id": "099-AR"},
 "attach": {"http": 200, "result": "success", "id": "v0.0.1-test"},
 "readback": {"行存在": true, "条款一致": true, "验收状态pending": true, "版本关联含行": true},
 "version": "v0.0.1-test",
 "result": "success"
}
```

`[exit=0]`。字段id由脚本按契约字段名解析得到（`tf-i-id`/`tf-i-clause`/`tf-i-acceptance`/`tf-i-implement`），没有硬编码。

## 4. 幂等：同参数重跑

```bash
export TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。","dir":""}'
awk '/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}' skills/tf-update/SKILL.md | bash
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "clause": "看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。",
 "steps": ["先读：行已存在且条款一致，跳过写入"],
 "result": "already_registered",
 "http": 200,
 "existing_clause": "看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。"
}
```

`[exit=0]`，无第二次写入，行数不变（仍为16，含演练行）。

## 5. 冲突：同id换条款

```bash
export TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加导出PDF的能力"}'
awk '/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}' skills/tf-update/SKILL.md | bash
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "clause": "看板增加导出PDF的能力",
 "steps": [],
 "result": "failed",
 "http": 200,
 "error": "行 id 已被占用且条款不同，拒绝覆盖",
 "existing_clause": "看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。"
}
```

`[exit=1]`：`failed`是终态，不重试、不覆盖。

## 6. 回读（登记后的真实行与版本）

```bash
curl -s $TF_BASE/api/tables/tf-indep/rows/099-AR \
  | python3 -c "import json,sys;print(json.dumps(json.load(sys.stdin)['row']['values'],ensure_ascii=False))"
curl -s $TF_BASE/api/tables/tf-ver/rows/v0.0.1-test \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['row']['values']['tf-v-indep'])"
```

```
{"tf-i-id": "099-AR", "tf-i-clause": "看板增加当前表格数据导出为CSV的能力：按当前筛选导出当前表格全部行，列头用字段名称。", "tf-i-acceptance": "pending", "tf-i-implement": "todo"}
["099-AR"]
```

## 7. 清理（摘关联 → 删行 → 删临时版本）

```bash
curl "${H[@]}" -X PATCH  $TF_BASE/api/agent/tables/tf-ver/rows/v0.0.1-test -d '{"values":{"tf-v-indep":[]}}'
curl "${H[@]}" -X DELETE $TF_BASE/api/agent/tables/tf-indep/rows/099-AR
curl "${H[@]}" -X DELETE $TF_BASE/api/agent/tables/tf-ver/rows/v0.0.1-test
```

```
{"result":"success","id":"v0.0.1-test"}
{"result":"success","id":"099-AR"}
{"result":"success","id":"v0.0.1-test"}
```

```bash
curl -s -o /dev/null -w '099-AR http=%{http_code}\n' $TF_BASE/api/tables/tf-indep/rows/099-AR
curl -s -o /dev/null -w 'v0.0.1-test http=%{http_code}\n' $TF_BASE/api/tables/tf-ver/rows/v0.0.1-test
```

```
099-AR http=404
v0.0.1-test http=404
```

## 8. 清理前后对比

清理前：`tf-indep 16`、`tf-ver 11`（含`v0.0.1-test`）。
清理后：

```
tf-indep 15
tf-ver 10 ['v0.1.0','v0.2.0','v0.3.0','v0.4.0','v0.4.1','v0.5.0','v0.5.1','v0.6.0','v0.6.1','v0.6.2']
```

`v0.6.0`逐字段（`sort_keys`后整行比较）：

```
{"tf-v-bug-clear": true, "tf-v-bug-open": 0, "tf-v-cond": false, "tf-v-dep": [], "tf-v-dep-count": 0,
 "tf-v-dev": 75.0, "tf-v-indep": ["008-AR", "009-AR", "010-AR", "015-AR"], "tf-v-note": "契约、计算与登记闭环",
 "tf-v-regress": true, "tf-v-scenes": 65.0, "tf-v-status": "planned", "tf-v-tasks": 52.0, "tf-v-ver": "v0.6.0"}
```

清理前后完全一致：演练没有污染正式版本，也没有留下测试行。

## 9. 本次登记的看板行（只改自己要的两行）

| 行 | 改动 | 回读值 |
|---|---|---|
| `009-AR` | 场景数21、任务总数15、`speckit-specify`=完成、`speckit-plan`=na、`speckit-task`=完成、`speckit-implement`=done、状态说明 | 回读一致 |
| `015-AR` | 场景数20、任务总数15、同上 | 回读一致 |

`验收状态`仍为`pending`：验收由需求方判定。

补充说明：`v0.6.0`行的`场景总数/任务总数/开发进度`是下游计算字段，随这两行登记被动重算（`10/10` → `65/52`，其中`010-AR`的场景数与任务数由backend同步登记）。`agent-tf-ftskills`的写入审计里只出现这两个 indep 行与这一处派生重算，没有对第三个业务行做过人工写入。


## 10. V060-02修复后复验（只读，不写业务行）

修复内容：目标版本不再自动选，`TF_PAYLOAD`必须带`version`；且该版本必须是`planned`、且晚于最近一个已发布版本。校验在写行之前完成，不通过就一行都不写。

```bash
export TF_BASE=http://192.168.1.155:8090 TF_AGENT=agent-tf-ftskills TF_PROJECT=tableflow
# ① 未指定版本
TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加当前表格数据导出为CSV的能力","dir":""}' \
  bash -c 'awk '"'"'/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}'"'"' skills/tf-update/SKILL.md | bash'
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "clause": "看板增加当前表格数据导出为CSV的能力",
 "steps": ["版本校验未通过：未写行、未挂载"],
 "result": "failed",
 "error": "未指定目标版本，拒绝登记（不自动选择版本）",
 "question": "这条需求要挂到哪个版本？当前 planned 版本：v0.2.0、v0.6.0、v0.6.1、v0.6.2",
 "latest_released": "v0.5.1"
}
```

`[exit=1]`：拒绝登记，且只问一个问题。

```bash
# ② 指定老版本 v0.2.0（planned但早于已发布v0.5.1）
TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加当前表格数据导出为CSV的能力","dir":"","version":"v0.2.0"}' \
  bash -c 'awk '"'"'/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}'"'"' skills/tf-update/SKILL.md | bash'
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "steps": ["版本校验未通过：未写行、未挂载"],
 "result": "failed",
 "error": "目标版本 v0.2.0 不晚于最近已发布版本 v0.5.1，拒绝登记",
 "latest_released": "v0.5.1"
}
```

`[exit=1]`：这正是V060-02的复现路径，修复后被挡在写行之前。

```bash
# ③ 指定不存在的版本
TF_PAYLOAD='{"kind":"indep","row_id":"099-AR","clause":"看板增加当前表格数据导出为CSV的能力","dir":"","version":"v9.9.9"}' \
  bash -c 'awk '"'"'/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}'"'"' skills/tf-update/SKILL.md | bash'
```

```
{
 "kind": "indep",
 "row_id": "099-AR",
 "table": "tf-indep",
 "steps": ["版本校验未通过：未写行、未挂载"],
 "result": "failed",
 "error": "目标版本 v9.9.9 不存在",
 "planned": ["v0.2.0", "v0.6.0", "v0.6.1", "v0.6.2"],
 "latest_released": "v0.5.1"
}
```

`[exit=1]`。三次拒绝都没有产生写入：执行前后`tf-ver`10行、`tf-indep`15行、`tf-dep`3行；`099-AR`为404；`v0.6.0`的关联仍是`["008-AR","009-AR","010-AR","015-AR"]`。
