# Prompt Engineering 说明

- `system.md`：身份、事实边界、确认门和 Prompt 注入约束。
- `intent_slots.md`：query/plan 分类、五场景与槽位结构。
- `tool_router.md`：Function Calling 的读写边界和上下文注入。
- `planner.md`：候选约束、排序与确认前禁止写入。
- `rag_answer.md`：有据回答和来源 Schema。

运行时输入包括用户消息、最近必要会话、工具 Schema 和工具/RAG 结果；输出为自然语言、tool calls 或结构化 plan card。后端最多执行六轮工具循环，并剥离模型试图提供的权限字段。
