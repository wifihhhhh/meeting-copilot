# Legacy scripts

This folder archives earlier command-line prototypes and experiment helpers.

The current Meeting Copilot application entry point is `app.py`, with production
logic under `pages/`, `services/`, `database/`, `scripts/`, and `tests/`.

Archived files:

- `rag.py`: earlier standalone RAG prototype.
- `evaluate_rag.py`: earlier standalone RAG evaluation driver.
- `llm_judge.py`: earlier standalone LLM-as-judge helper.
- `precision.py`: earlier standalone precision/recall utility.
- `extract_ds.py`: earlier batch extraction script.
- `json_to_txt.py`: earlier JSON-to-text conversion script.
- `tasks.py`: earlier task extraction script based on `tasks.json`.
- `tasks_manager.py`: earlier CLI task manager prototype.

These files are kept for traceability and comparison only. They are not required
by the Streamlit web application.
