from __future__ import annotations

import argparse

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from database.repository import MeetingRepository
from services.dataset_importer import DatasetImporter
from services.meeting_rag import MeetingRAG, VectorStoreUnavailableError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import the real meeting dataset into SQLite and ChromaDB.")
    parser.add_argument("--processed-dir", default=str(PROCESSED_DATA_DIR))
    parser.add_argument("--raw-dir", default=str(RAW_DATA_DIR))
    parser.add_argument("--source", default="real_dataset")
    parser.add_argument("--index", action="store_true", help="Also rebuild ChromaDB vectors.")
    parser.add_argument("--private", action="store_true", help="Import as private demo-user data.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repository = MeetingRepository()
    rag = None
    if args.index:
        try:
            rag = MeetingRAG(repository=repository)
        except VectorStoreUnavailableError as exc:
            print(f"ChromaDB unavailable: {exc}")
            return 2

    result = DatasetImporter(repository=repository, rag=rag).import_directory(
        args.processed_dir,
        args.raw_dir,
        source=args.source,
        shared=not args.private,
    )
    print(
        f"total={result.total} created={result.created} updated={result.updated} "
        f"failed={result.failed} indexed_chunks={result.indexed_chunks}"
    )
    for error in result.errors:
        print(f"ERROR {error}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
