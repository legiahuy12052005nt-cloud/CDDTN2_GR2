"""Xuất hợp đồng API ra docs/openapi.json (chạy lại mỗi khi sửa backend/schemas/api.py)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.main import app
(ROOT / "docs" / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print("paths:", len(app.openapi()["paths"]))
