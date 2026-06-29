# 系统架构说明

Meeting Copilot 分为五层：

1. UI 层：Streamlit 多页面应用，负责输入、编辑、导出、历史检索和问答。
2. AI 能力层：OllamaClient、MeetingExtractor、MinutesFormatter 负责 LLM 调用、结构化输出和纪要生成。
3. RAG 检索层：EmbeddingService、VectorStore、RAGService 负责向量化、ChromaDB 检索和上下文增强回答。
4. 数据持久化层：SQLite 保存会议原文、结构化 JSON、Markdown 纪要和问答记录。
5. 评估实验层：EvaluationService 对比人工标注，计算 Precision、Recall、F1。

这个设计体现了 Prompt Engineering、结构化输出、Embedding、向量数据库、RAG 和工程分层。
