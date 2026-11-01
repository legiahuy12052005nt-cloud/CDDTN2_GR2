"""Kiểm thử chạy trên thư mục tạm (FRI_WORK_DIR) để không ghi đè dữ liệu, mô hình thật của máy chủ."""
import os
import tempfile

os.environ["FRI_WORK_DIR"] = tempfile.mkdtemp(prefix="fri_test_")
os.environ.pop("GEMINI_API_KEY", None)
