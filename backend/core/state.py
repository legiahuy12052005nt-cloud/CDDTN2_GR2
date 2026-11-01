"""Trạng thái phiên làm việc (ứng dụng một người dùng – QĐ-01).

Giữ trong bộ nhớ các kết quả của pipeline để API đọc nhanh (NFR-02) và nạp lại từ đĩa
khi khởi động máy chủ (QĐ-02: CSV/joblib/JSON), nên tắt máy chủ không mất kết quả.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import joblib
import pandas as pd

from backend.core import config as C

P = C.DATA_PROCESSED
FILES = {
    "reviews": P / "reviews_clean.csv",
    "meta": P / "dataset_meta.json",
    "eda": P / "eda_cache.json",
    "products": P / "products.csv",
    "topics": P / "topics.json",
    "review_topics": P / "review_topics.csv",
    "forecast": P / "forecast_overall.json",
    "risk_backtest": P / "risk_backtest.json",
    "predictions": P / "predictions.csv",
    "registry": C.MODELS_DIR / "model_registry.json",
    "model": C.MODELS_DIR / "model_bundle.joblib",
    "topic_model": C.MODELS_DIR / "topic_bundle.joblib",
    "ai_cache": C.CACHE_DIR / "ai_insights.json",
}


class AppState:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset_memory()

    def reset_memory(self):
        self.df: pd.DataFrame | None = None
        self.meta: dict = {}
        self.eda: dict = {}
        self.model: dict | None = None        # vectorizer, model, lr, weights, vocab
        self.registry: dict | None = None
        self.topic_model: dict | None = None  # vectorizer, nmf, names
        self.topics: list | None = None
        self.review_topics: pd.DataFrame | None = None
        self.products: pd.DataFrame | None = None
        self.forecast: dict | None = None
        self.risk_backtest: dict | None = None
        self.predictions: pd.DataFrame | None = None
        self.forecast_cache: dict = {}

    # ------------------------------------------------------------------ trạng thái
    @property
    def dataset_loaded(self) -> bool:
        return self.df is not None

    @property
    def model_ready(self) -> bool:
        return self.model is not None

    @property
    def version(self) -> str:
        return self.meta.get("dataset_version", "")

    def meta_block(self, filters: dict | None = None) -> dict:
        return {"dataset_version": self.version, "filters": {k: v for k, v in (filters or {}).items() if v not in (None, "")}}

    # ------------------------------------------------------------------ nạp từ đĩa
    def load_from_disk(self) -> None:
        with self.lock:
            self.reset_memory()
            if not FILES["reviews"].exists() or not FILES["meta"].exists():
                return
            self.df = read_clean(FILES["reviews"])
            self.meta = _json(FILES["meta"])
            self.eda = _json(FILES["eda"]) if FILES["eda"].exists() else {}
            if FILES["model"].exists() and FILES["registry"].exists():
                self.model = joblib.load(FILES["model"])
                self.registry = _json(FILES["registry"])
            if FILES["topic_model"].exists() and FILES["topics"].exists():
                self.topic_model = joblib.load(FILES["topic_model"])
                self.topics = _json(FILES["topics"])
                self.review_topics = pd.read_csv(FILES["review_topics"]) if FILES["review_topics"].exists() else None
                if not self.topics:
                    self.topic_model = self.topics = self.review_topics = None
            if FILES["products"].exists():
                self.products = pd.read_csv(FILES["products"], dtype={"product_id": str, "first_month": str, "last_month": str, "as_of": str})
                self.products["reason"] = self.products.reason.fillna("")
                self.products["signal"] = self.products.signal.fillna("") if "signal" in self.products else ""
            if FILES["forecast"].exists():
                self.forecast = _json(FILES["forecast"])
            if FILES["risk_backtest"].exists():
                self.risk_backtest = _json(FILES["risk_backtest"])
            if FILES["predictions"].exists():
                self.predictions = pd.read_csv(FILES["predictions"])

    def clear_disk(self) -> list[str]:
        removed = []
        for key, path in FILES.items():
            if path.exists():
                path.unlink()
                removed.append(str(path.relative_to(C.BASE_DIR)) if path.is_relative_to(C.BASE_DIR) else path.name)
        with self.lock:
            self.reset_memory()
        return removed


def read_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"product_id": str, "user_key": str, "summary": str, "text": str,
                                  "year_month": str, "review_date": str, "sentiment": str},
                     keep_default_na=False, na_values={"helpful_ratio": [""]})
    return df


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, default=_default), encoding="utf-8")


def _default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    return str(o)


STATE = AppState()
