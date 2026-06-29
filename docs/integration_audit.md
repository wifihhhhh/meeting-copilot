# 正式脚本与 Web 项目整合审计

## 1. 审计目标

本次整合不按文件新旧直接替换，而是以功能为单位，对根目录正式脚本与当前 `services/`、`database/`、`pages/` 实现逐项核对。每项功能只能作出以下决定之一：

- 保留当前实现；
- 使用正式脚本替换；
- 融合双方优点；
- 保留为独立实验或批处理工具。

旧文件在功能等价验证、真实数据实验和迁移记录完成前不删除。

## 2. 安全基线

- 原项目备份：`C:\Users\Tina\Desktop\meeting-copilot_backup_20260618_214353`
- 备份校验：源目录与备份均为 512 个文件、8,884,760 字节。
- 集成分支：`integration/formal-pipeline`
- Python 编译检查：通过。
- pytest 基线：`12 passed, 2 skipped`。
- Git 基线：原工作区 `main` 落后远端 1 个提交；本地已有 `README.md` 修改，整合过程不得覆盖。

## 3. 当前数据审计

| 数据 | 数量 | 当前实际使用情况 |
|---|---:|---|
| `data/samples/*.txt` | 10 | 被纪要生成页直接读取，属于模拟演示数据 |
| `data/M*.txt` | 36 | 真实会议原文，目前未被 Web 或正式脚本默认路径读取 |
| `database/M*.json` | 36 | 真实会议结构化结果，目前未写入 SQLite，也未被 Web 读取 |
| `data/annotations/*.json` | 2 | 评估页展示文件名，但没有形成 10 场以上批量实验 |
| `data/evaluation_questions/rag_questions.json` | 1 | 当前评估脚本仍使用代码内置测试问题，尚未统一读取 |
| `database/meeting_copilot.db` | 1 | Web 正式业务数据库 |
| `chroma_db/` | 1 | Web 当前向量库目录 |

正式脚本当前写死 `./36`、`./36_json`、`./36_txt`、`./10会议_人工标注` 等路径，与仓库实际目录不一致。

## 4. 重复功能逐项取舍

### 4.1 会议结构化抽取

| 对比项 | 当前 Web 实现 | 根目录正式脚本 |
|---|---|---|
| 文件 | `services/meeting_extractor.py` | `extract_ds.py` |
| 模型 | Ollama Qwen2.5 | DeepSeek API |
| 输出约束 | JSON Schema + Pydantic | Prompt JSON + 手工解析 |
| 稳定性 | 异常分类、JSON 修复、规则兜底 | 重试、日志、批量断点式输出 |
| 数据能力 | 单场交互式生成 | 36 场真实数据批处理 |

决定：**融合**。

保留当前 `MeetingMinutes`、JSON Schema、Pydantic、异常处理和规则兜底；迁移 `extract_ds.py` 的批量扫描、参与人/时间预处理、日志和逐文件保存能力。课程正式主模型仍使用 Ollama Qwen2.5，DeepSeek 作为可选对比实验，不作为默认依赖。

验收：36 场真实会议均经过统一 Schema 校验；失败样本必须生成结构化错误报告。

### 4.2 JSON 转可读纪要

| 对比项 | 当前 Web 实现 | 根目录正式脚本 |
|---|---|---|
| 文件 | `minutes_formatter.py`、`export_service.py` | `json_to_txt.py` |
| 优势 | 网页编辑，Markdown/JSON/PDF 导出 | 批量转换，兼容旧中文字段 |

决定：**融合**。

保留当前格式化与导出服务；提取旧脚本的中文字段兼容和批量处理能力，放入 Schema Adapter 与批处理命令，不在业务层维护第二套格式。

### 4.3 Embedding 与向量存储

| 对比项 | 当前 Web 实现 | 根目录正式脚本 |
|---|---|---|
| 文件 | `embedding_service.py`、`meeting_rag.py` | `rag.py` |
| Embedding | 384 维 Hash，无模型依赖 | BGE-M3 1024 维语义向量 |
| 粒度 | 700 字切块，重叠 120 | 一场会议一个向量 |
| 权限 | `user_id` 过滤 | 无账号隔离 |
| 失败行为 | 明确异常 | 返回全零向量并继续执行 |

决定：**融合，以当前架构为主体**。

引入 BGE-M3、L2 归一化、可配置阈值；保留当前切块、来源元数据、用户隔离、会议删除联动和 Hash 离线兜底。拒绝全零向量入库、硬编码模型和整场单向量方案。

验收：Hash 与 BGE-M3 使用不同版本化 Chroma collection；索引可重建；旧索引不被覆盖。

### 4.4 RAG 检索与回答

当前实现提供 Top-K、来源、会议范围过滤和问答记录；`rag.py` 提供 LLM 关键词提取、相似度阈值和候选回退。

决定：**融合**。

增加可选关键词增强、阈值过滤和阈值以下最高候选回退；保留当前 Prompt 文件、来源格式和数据库记录。

验收：使用统一测试问题比较 Hash/BGE-M3、Top-K 和阈值配置，报告 Recall@K、来源命中率、延迟与 LLM-as-Judge。

### 4.5 抽取评估

| 对比项 | 当前 Web 实现 | 根目录正式脚本 |
|---|---|---|
| 文件 | `evaluation_service.py` | `precision.py` |
| 匹配 | 标准化后集合精确匹配 | 关键词覆盖相似度 + 贪心匹配 |
| 执行 | 单次上传 | 文件夹批量评估 |

决定：**融合**。

精确匹配保留为严格基线；增加模糊匹配作为正式指标，并记录匹配阈值。批量结果保存到 `evaluation_results` 和导出文件。

### 4.6 RAG LLM-as-Judge

`llm_judge.py` 和 `evaluate_rag.py` 在当前 Web 中没有等价实现。

决定：**迁移为新增正式能力**。

保留多维评分、硬规则和 CSV 导出；重构为 `LLMJudgeService`，避免直接依赖根目录全局变量。评估页面增加 RAG 评估与对比实验视图。

### 4.7 待办提取与管理

| 对比项 | 当前 Web 实现 | 根目录正式脚本 |
|---|---|---|
| 文件 | SQLite `action_items`、历史页看板 | `tasks.py`、`tasks_manager.py` |
| 存储 | SQLite，用户隔离 | `tasks.json` |
| 能力 | 状态更新、看板 | 筛选、逾期、日期统计、负责人统计、提醒 |

决定：**融合，以 SQLite 为唯一正式存储**。

迁移筛选、逾期判断、统计和提醒算法；不在正式 Web 中继续维护 `tasks.json`。旧脚本保留作命令行原型，直到功能等价。

## 5. 数据与权限方案

建议采用双层数据：

- 36 场课程真实数据：系统共享只读语料；
- 用户自行上传数据：保持当前私有读写权限。

拟为会议增加 `source`、`external_id`、`is_shared` 字段。`source + external_id` 用于幂等导入，避免重复保存；共享语料只保存一份，不为每个账号复制。

任何数据库迁移执行前必须先在工作区副本验证，并保留原桌面数据库备份。

## 6. 对比实验矩阵

| 实验 | 对照配置 | 指标 |
|---|---|---|
| Embedding | Hash vs BGE-M3 | Recall@K、来源命中率、延迟 |
| 阈值 | 0.20 / 0.30 / 0.40 | 命中率、无答案率、Judge 分数 |
| Top-K | 3 / 5 / 10 | Recall@K、上下文长度、延迟 |
| 抽取模型 | Qwen2.5-1.5B / Qwen2.5-7B | P/R/F1、完整性、耗时 |
| 兜底策略 | 规则 / LLM / LLM+规则 | 成功率、P/R/F1、耗时 |
| 数据集 | 10 个模拟样例 / 36 场真实会议 | 泛化差异、失败类型 |

## 7. 迁移原则

1. 先写适配器和测试，再接入页面。
2. 不直接覆盖 SQLite、ChromaDB 或现有用户数据。
3. 不将 DeepSeek 密钥或本地数据库提交 Git。
4. 不在功能等价验证前删除根目录脚本。
5. 每项取舍必须在本文件补充实现位置、测试结果和最终结论。
6. 合并后的 pytest 结果不得低于基线 `12 passed, 2 skipped`。

## 8. 当前实施与验证记录（2026-06-18）

- 36 份旧 JSON 已通过 `schema_adapter.py` 转换为统一 `MeetingMinutes`，并全部通过 Pydantic 校验。
- SQLite 已增加 `source`、`external_id`、`is_shared` 兼容迁移；真实数据连续导入两次均保持 36 条，证明幂等。
- BGE-M3 Provider 已实现维度校验、L2 归一化和全零向量拒绝；Hash 继续作为离线兜底，两者使用独立 collection。
- 待办筛选、逾期和统计已迁移到 SQLite 服务层；抽取模糊评估与本地 Ollama Judge 已接入评估页。
- 正式 RAG 数据集已迁移为 10 条带人工来源 ID 的真实问题；运行器输出逐题 CSV、汇总 JSON 和 Markdown 报告。
- 当前完整测试结果为 `28 passed, 2 skipped`，高于原始基线。

### 8.1 首轮 RAG 基线结论

本机缺少 ChromaDB 且 Ollama 服务未运行。正式运行器因此使用明确标注的 `in_memory_exact_cosine` 后端完成 Hash 精确余弦基线；该后端复用正式切块、Hash 向量和阈值/回退策略，不伪装成生产 Chroma 检索。BGE-M3 组记录为不可用，不生成替代分数。

Hash 首轮在 10 条真实问题上的来源命中率为 70%，平均 Recall@K 为 0.366667。0.20、0.30、0.40 均高于多数 Hash 相似度，所有配置触发最高候选回退，平均实际返回数为 1，因此 Top-3/5/10 结果相同。结论是：BGE 阈值不能直接套用于 Hash；Hash 应单独标定阈值或仅作为无阈值离线兜底。完整结果位于 `data/evaluation/formal_baseline/`。
