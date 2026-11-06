# 需求质量 Checklist: 只读状态看板（v0）

**Purpose**: 实现前对 spec / plan / data-model / contracts 做一次需求质量自查，只查会导致返工或验收争议的点
**Created**: 2026-11-06
**Feature**: [spec.md](../spec.md)

**Note**: 本清单由 `/speckit-checklist` 生成，用于检查"需求写得好不好"，不是实现测试。
**Review Ownership**: 清单归评审人所有。只有评审人确认该需求质量条目成立时才标记 `[x]`。
**Marker Semantics**: `[x]` 表示需求质量条目已被评审并通过，不代表实现完成。

## 验收口径可测性

- [ ] CHK001 500ms 的计时终点是否定义到具体一帧（第14行首次可见 vs 字体与样式就绪 vs 网络空闲）？[Clarity, Spec §SC-001]
- [ ] CHK002 50fps 与"无超过50ms长任务"的采样窗口、滚动方向与滚动距离是否定义？[Clarity, Spec §SC-002]
- [ ] CHK003 "14行"验收样本与 SC-005 的"20项目 / 500行"上限之间是什么关系（样本合格是否代表上限合格）？[Consistency, Spec §SC-001 / §SC-005]
- [ ] CHK004 SC-004 的"命中率 100%"如何判定：刷新几次、是否包含"写入与读取同时发生"的情形？[Measurability, Spec §SC-004]

## 数据与 schema 边界

- [ ] CHK005 四种类型的值形态是否逐一定义到位：number 的精度与非法值、datetime 的时区与缺省格式、enum 的 label 缺失？[Completeness, data-model §4]
- [ ] CHK006 未知 type 回退纯文本，是否与"新增 type 属功能变更、走 spec"的边界冲突（回退算不算已经支持）？[Consistency, Spec §FR-005 / research D8]
- [ ] CHK007 `visible = 0` 的语义在 spec（不显示）与接口（不返回）之间是否一致，删除列与隐藏列是否被区分？[Consistency, Spec §FR-003 / data-model §5.3]
- [ ] CHK008 `row_records.data` 中"键不存在"与"值为 null"是否被要求区分，还是都按空单元格处理？[Clarity, data-model §3 / §4]

## 只读与无缓存约束

- [ ] CHK009 "无读缓存"的可判定边界是否明确到具体机制（HTTP 缓存头、浏览器 bfcache、服务进程内存、前端状态复用）？[Clarity, Spec §FR-002 / 宪法原则 II]
- [ ] CHK010 "v0 无写路径"的判定方式是否定义（路由清单检查、代码检索、还是数据库只读连接）？[Measurability, 宪法原则 I]
- [ ] CHK011 未定义的路径与非 GET 方法应返回 404 还是 405，是否已有明确口径？[Ambiguity, contracts/api.md]

## 多项目与状态一致性

- [ ] CHK012 切换项目时，新数据返回前页面显示什么（清空 / 骨架 / 保留旧表）是否有明确规定？[Clarity, Spec US2 场景2]
- [ ] CHK013 首屏默认选中哪个项目是否定义（第一个 / 上次访问 / URL 参数）？[Gap, Spec US2 场景1]
- [ ] CHK014 快速连续切换项目产生的请求竞态，是否在需求层被要求处理（丢弃过期响应）？[Coverage, Gap]

## 异常与恢复

- [ ] CHK015 数据存储"不可达或超时"的超时阈值是否定义，还是只写"超时"？[Gap, Spec §FR-008]
- [ ] CHK016 503 的触发边界是否枚举（库文件缺失、只读打开失败、查询异常、WAL 文件不可读）？[Completeness, contracts/api.md §2]
- [ ] CHK017 重试按钮的行为是否定义（只重试当前项目、还是整页重载并重新取项目列表）？[Clarity, Spec §FR-008]

## Notes

- 本清单共 17 条，覆盖 5 个维度，定位为"实现前 10 分钟自查"，不替代 `/speckit-analyze` 的跨产物一致性检查。
- `[x]` 由评审人填写；生成命令不预置勾选状态。
- 实现阶段读取本清单状态，但不会修改标记。
