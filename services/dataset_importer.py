from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from database.repository import DEFAULT_USER_ID, MeetingRepository
from services.meeting_rag import MeetingRAG
from services.minutes_formatter import format_minutes
from services.schema_adapter import load_legacy_meeting


@dataclass
class DatasetImportResult:
    total: int = 0
    created: int = 0
    updated: int = 0
    indexed_chunks: int = 0
    failed: int = 0
    meeting_ids: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DatasetImporter:
    def __init__(
        self,
        repository: MeetingRepository | None = None,
        rag: MeetingRAG | None = None,
    ) -> None:
        self.repository = repository or MeetingRepository()
        self.rag = rag

    def import_directory(
        self,
        processed_dir: str | Path,
        raw_dir: str | Path,
        *,
        source: str = "real_dataset",
        shared: bool = True,
        owner_user_id: int = DEFAULT_USER_ID,
    ) -> DatasetImportResult:
        processed_dir = Path(processed_dir)
        raw_dir = Path(raw_dir)
        json_files = sorted(processed_dir.glob("M*.json"))
        result = DatasetImportResult(total=len(json_files))

        for json_path in json_files:
            try:
                adapted = load_legacy_meeting(json_path, raw_dir=raw_dir, source=source)
                minutes_json = adapted.minutes.model_dump()
                markdown = format_minutes(minutes_json)
                meeting_id, created = self.repository.upsert_external_meeting(
                    external_id=adapted.external_id,
                    source=adapted.source,
                    raw_text=adapted.raw_text,
                    minutes_json=minutes_json,
                    minutes_markdown=markdown,
                    is_shared=shared,
                    owner_user_id=owner_user_id,
                )
                result.meeting_ids.append(meeting_id)
                if created:
                    result.created += 1
                else:
                    result.updated += 1

                if self.rag is not None:
                    result.indexed_chunks += self.rag.index_meeting(
                        meeting_id,
                        adapted.minutes.title,
                        adapted.minutes.date,
                        markdown,
                        user_id=owner_user_id,
                        is_shared=shared,
                        source=adapted.source,
                        external_id=adapted.external_id,
                    )
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{json_path.name}: {exc}")
        return result
