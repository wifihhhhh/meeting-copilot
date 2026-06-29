from pathlib import Path


def load_text_from_upload(uploaded_file: object) -> str:
    data = uploaded_file.getvalue()
    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def load_text_file(path: str | Path) -> str:
    file_path = Path(path)
    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="ignore")
