# 答辩提纲

## 项目解决的问题

会议结束后人工整理纪要耗时，且容易遗漏决议和待办。本系统把会议记录自动转为结构化纪要，并支持历史会议问答。

## 用到的课程知识

- Prompt Engineering：设计抽取、问答、评估 Prompt。
- 结构化输出：LLM 输出 JSON，系统校验并格式化。
- RAG：历史会议向量检索 + 上下文增强生成。
- 向量检索：ChromaDB 保存会议纪要 chunk。
- 工程实践：Streamlit + 服务层 + SQLite + 测试。

## 可能被问到的问题

1. 为什么使用 ChromaDB？
   - 轻量、易持久化，适合本地课程项目。
2. 为什么还需要 SQLite？
   - SQLite 存业务数据，ChromaDB 存语义向量，两者职责不同。
3. 如果 LLM 输出 JSON 错了怎么办？
   - 使用 schema validator 归一化字段，并预留 repair_json_prompt。
4. 数据量扩大 10 倍怎么办？
   - 增加分页、异步索引、批量 embedding，并优化 chunk size 和 Top-K。
