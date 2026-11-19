# Quickstart / 验收记录：左侧项目导航与全局刷新（v0.5.0）

**日期**: 2026-11-19
**环境**: 本地 8000/5173，Chrome 1280×800；临时库 40项目用于侧栏滚动验收

## 1. 复现命令

```bash
cd frontend && npx tsc --noEmit && npm run build
cd ../backend && .venv/bin/pytest -q
cd .. && python3 scripts/contrast_check.py
python3 scripts/perf_check.py http://127.0.0.1:5173/ --rows 14
```

交互核验（浏览器控制台）：

1. 切换项目、切换表格、输入筛选词，点页头「刷新」，核对项目/表格/筛选不变，Network 三个GET各一次。
2. 用临时库造40项目，核对侧栏 `scrollHeight > clientHeight` 且 `overflow-y: auto`。
3. 在页面里把 `window.fetch` 延迟400ms再点刷新，读按钮 `aria-busy` / `disabled` / 文案。
4. 停后端再点刷新，核对错误态；恢复后端点刷新，核对自动恢复。

## 2. 结果

| 项 | 结果 |
|---|---|
| `npx tsc --noEmit` | 零错误 |
| `npm run build` | 成功，44模块，643ms |
| `pytest -q` | 97 passed |
| `contrast_check.py` | 5项全部达标 |
| 首屏（4行样本） | 87ms（行数不足14，仅参考） |
| 滚动 | 60.4fps，>50ms长任务0个 |
| 布局 | 1280×800：侧栏216px + 内容1016px，无横向溢出 |
| 侧栏滚动 | 40项目：`scrollHeight=1561 > clientHeight=788`，`overflow-y: auto` |
| 选中态 | 当前项目 `aria-current="page"`，背景 `#eef6ff` + 强调色文字 |
| 刷新请求 | `GET /api/projects`、`GET /api/projects/{id}/tables`、`GET /api/tables/{id}/table` 各1次 |
| 刷新中 | `aria-busy="true"`、`disabled=true`、文案「⟳刷新中」 |
| 刷新后 | 项目`demo`/表格「独立规格需求」/筛选`UD-04`均保留，计数`1/1 条` |
| 离线刷新 | 显示「读取失败」+「重试」，刷新按钮可点；后端恢复后点刷新自动恢复（2项目、3表格） |
| 返回按钮 | 刷新结束恢复 `aria-busy="false"`、可点、文案「⟳刷新」 |

截图（`.tmp-shots/` 已 gitignore）：`007-layout.png`、`007-sidebar-40.png`。

## 3. 结论

- 项目列表已改为左侧竖排导航，内容区占据右侧剩余宽度；40项目时侧栏内部滚动，表格区宽度不变。
- 页头刷新按钮重拉项目→表格→当前表数据，保留选中项与筛选词，不闪骨架；离线失败进入既有错误态且可重试恢复。
- 不新增依赖、不改接口与数据模型，性能与对比度基线未回退。

## 4. 回退方式

回退本次提交即可；无数据迁移、无配置项、无 localStorage 键变化。

## 5. 上线记录（2026-11-19）

- 发布前备份：`/srv/tableflow/deploy/data/tableflow.db.bak-20261119-093510`（容器内 sqlite backup API 生成，`integrity_check=ok`，7项目），并取回本地 `.tmp-shots/tableflow-predeploy-20261119-093510.db`。
- 部署：`bash deploy/deploy.sh`（默认模式，未带`--seed`）；镜像`tableflow:0.5.0`，数据目录`deploy/data`未重建。
- 发布后核对：7项目、21张表行数与部署前逐一一致；前端资源`index-BvIc8YMP.js`；线上点刷新发3个GET，当前项目/表格保持。
- 回滚：把`deploy/docker-compose.yml`的`image`改回`tableflow:0.4.1`后重新`up -d`；数据恢复用备份文件替换`deploy/data/tableflow.db`（先停容器，并删除`-wal`/`-shm`）。
