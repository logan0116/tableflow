## 为什么改

<!-- 问题是什么，为什么现在要改；不要只列文件 -->

## 改了什么

<!-- 关键实现点；契约/接口/数据模型有变化时写明兼容性 -->

## 怎么验证

<!-- 测试名、curl 输出、截图；契约改动附 render_rules 的重生成结果 -->

```bash
cd backend && uv run pytest -q
cd frontend && npm run build
```

## 自查

- [ ] 没有提交 `data/*.db`、`deploy/.env`、明文密钥
- [ ] 契约改动已重新生成 `rules.py`（未手改生成物）
- [ ] 行为变化带测试或可核验证据
