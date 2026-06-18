from services.export_service import ExportService


def test_export_markdown(tmp_path):
    service = ExportService(export_dir=tmp_path)
    path = service.export_markdown("# 测试", "测试会议")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "# 测试"
