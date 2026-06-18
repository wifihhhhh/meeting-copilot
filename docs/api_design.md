# 服务接口设计

## MeetingExtractor

- 输入：会议原文 `str`
- 输出：结构化 JSON，包括 `title`、`participants`、`topics`、`decisions`、`action_items`

## RAGService

- `index_meeting(meeting_id, title, meeting_date, minutes_markdown)`
- `answer(question, use_llm=True, top_k=5)`

## MeetingRepository

- `create_meeting(...)`
- `update_meeting(...)`
- `list_meetings(keyword="")`
- `get_meeting(meeting_id)`
- `keyword_search(query, limit=5)`

## ExportService

- `export_markdown(minutes_markdown, title)`
- `export_json(minutes_json, title)`
- `export_pdf(minutes_markdown, title)`
