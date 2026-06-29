# 数据目录

| 目录 | 用途 |
|---|---|
| `raw/` | 36 场真实会议转写原文，只作为输入数据 |
| `processed/` | 旧正式脚本生成的 36 份结构化 JSON |
| `samples/` | Streamlit 页面用于快速演示的 10 个模拟样例 |
| `annotations/` | 人工标注数据 |
| `evaluation_questions/` | RAG 测试问题 |
| `evaluation/` | 后续对比实验输出，生成文件默认不提交 |

`services/schema_adapter.py` 负责把 `processed/` 中的旧中文字段转换为统一的 `MeetingMinutes` Pydantic 模型。原始文件在整合验收前继续保留，避免迁移过程中丢失数据。
