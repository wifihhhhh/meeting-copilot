import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import EXPORT_DIR


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fa5-]+", "_", text.strip())[:40]
    return slug or "meeting"


class ExportService:
    def __init__(self, export_dir: Path = EXPORT_DIR) -> None:
        self.export_dir = export_dir
        for name in ("markdown", "pdf", "json"):
            (self.export_dir / name).mkdir(parents=True, exist_ok=True)

    def export_markdown(self, minutes_markdown: str, title: str) -> Path:
        path = self.export_dir / "markdown" / self._filename(title, "md")
        path.write_text(minutes_markdown, encoding="utf-8")
        return path

    def export_json(self, minutes_json: dict[str, Any], title: str) -> Path:
        path = self.export_dir / "json" / self._filename(title, "json")
        path.write_text(json.dumps(minutes_json, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def export_pdf(self, minutes_markdown: str, title: str) -> Path:
        path = self.export_dir / "pdf" / self._filename(title, "pdf")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfgen import canvas

            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            c = canvas.Canvas(str(path), pagesize=A4)
            width, height = A4
            y = height - 50
            c.setFont("STSong-Light", 11)
            for raw_line in minutes_markdown.splitlines():
                line = raw_line.replace("#", "").replace("*", "").strip()
                if not line:
                    y -= 10
                    continue
                for part in _wrap_line(line, 42):
                    c.drawString(50, y, part)
                    y -= 18
                    if y < 50:
                        c.showPage()
                        c.setFont("STSong-Light", 11)
                        y = height - 50
            c.save()
        except Exception:
            path.write_text(minutes_markdown, encoding="utf-8")
        return path

    @staticmethod
    def _filename(title: str, suffix: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe_slug(title)}_{timestamp}.{suffix}"


def _wrap_line(line: str, width: int) -> list[str]:
    return [line[index : index + width] for index in range(0, len(line), width)] or [""]
