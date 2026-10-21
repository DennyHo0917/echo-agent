# 上下文压缩与 Spill

模型上下文有上限。Echo Agent 用历史压缩缩短输入，用 Spill 保存过大的工具输出；长期记忆整合另有独立的提交边界。

## 对话压缩

ContextStage 读取 `Session.get_history()` 得到当前活动历史，在接近模型窗口时交给 ConversationCompressor。压缩在副本上裁剪较旧的媒体和工具内容，保留头部与近期消息，为中间部分生成摘要。只有完整可用的摘要才允许替换活动历史；摘要失败、截断、过滤或冷却时保留原文和媒体引用，不保存缺少中段内容的头尾拼接。

`last_consolidated` 属于长期记忆整合的已提交边界，压缩不会通过推进它来假装记忆已写入。历史边界会对齐 assistant 工具调用及结果，避免把孤立工具结果交给模型。

触发与预算由 `compression`、模型窗口及 `session.compression_window_cap` 控制。压缩失败保留数据，但不能保证超长输入仍能被模型接受；可恢复摘要模型后重试或显式开始新会话。

## Spill 溢写

启用 `spill.enabled` 后，大工具输出写入工作区内专用的 `storage.spill_dir`，对话保留短预览和引用。用 `read_spill` 按 `offset`/`limit` 或 `pattern` 读取；跨会话引用仍须通过作用域检查，不能靠猜文件名访问其他会话数据。

`spill.max_inline_chars` 控制内联阈值，`max_total_mb`、`retention_days` 和 `sweep_interval_hours` 控制容量与清理。引用不是永久备份；保留期限后的原文可能已清理。用户应交付的文档使用 artifact 工具链定稿及投递，避免只留下临时 Spill 引用。

## 相关文档

- [记忆系统](memory-system.md)
- [任务与规划](../guides/tasks-planning.md)
- [工具参考](../reference/tools.md)
