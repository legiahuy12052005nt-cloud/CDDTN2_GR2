"""Tạo bộ dữ liệu mẫu 100.000 dòng (định dạng gốc 10 cột) cho nút "Dùng dữ liệu mẫu" (FR-06).

Chạy: python scripts/make_sample.py   (cần backend/data/raw/Reviews.csv tải từ Kaggle)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from backend.core import config as C

raw = pd.read_csv(C.DATA_RAW / "Reviews.csv")
raw.sample(C.TRAIN_SAMPLE_MAX, random_state=C.RANDOM_STATE).sort_values("Id").to_csv(C.DATA_SAMPLE / "reviews_sample_100k.csv", index=False)
print("Đã tạo", C.DATA_SAMPLE / "reviews_sample_100k.csv")
