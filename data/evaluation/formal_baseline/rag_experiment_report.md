# RAG 正式对比实验报告

- 运行时间：2026-06-18T22:52:30+08:00
- 真实会议：36 场
- 评估问题：10 条
- 指标说明：来源命中率表示至少命中一个人工标注来源；Recall@K 衡量全部标注来源的覆盖；参考答案覆盖率为关键词覆盖基线，不等同于 LLM Judge。

| Embedding | 检索后端 | Top-K | 阈值 | 成功/总数 | 来源命中率 | Recall@K | 答案覆盖率 | 平均相似度 | 实际返回数 | 平均耗时(ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hash | in_memory_exact_cosine | 3 | 0.20 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.0331 |
| hash | in_memory_exact_cosine | 3 | 0.30 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.5465 |
| hash | in_memory_exact_cosine | 3 | 0.40 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.0634 |
| hash | in_memory_exact_cosine | 5 | 0.20 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.2708 |
| hash | in_memory_exact_cosine | 5 | 0.30 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.3886 |
| hash | in_memory_exact_cosine | 5 | 0.40 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 2.8811 |
| hash | in_memory_exact_cosine | 10 | 0.20 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.2895 |
| hash | in_memory_exact_cosine | 10 | 0.30 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 3.0822 |
| hash | in_memory_exact_cosine | 10 | 0.40 | 10/10 | 0.7 | 0.366667 | 0.432777 | 0.176992 | 1.0 | 2.8847 |

## 未运行配置

- `bge-m3`：Ollama Embedding 请求失败：HTTPConnectionPool(host='localhost', port=11434): Max retries exceeded with url: /api/embed (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x000001856E87B0E0>: Failed to establish a new connection: [WinError 10061] 由于目标计算机积极拒绝，无法连接。'))

原始逐题结果见 `rag_experiment_rows.csv`，机器可读汇总见 `rag_experiment_summary.json`。
