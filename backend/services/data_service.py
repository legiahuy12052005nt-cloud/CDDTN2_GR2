"""DataService – kiểm tra cấu trúc, báo cáo chất lượng, làm sạch dữ liệu đánh giá.

Hiện thực bước 1–3 của pipeline (báo cáo buổi 4, bảng 4.7) theo thiết kế chi tiết
buổi 5 (mục 2.3 – quy tắc làm sạch R1–R9). Các notebook phân tích dùng chung
module này nên số liệu trong báo cáo và số liệu ứng dụng hiển thị là một.
"""
from __future__ import annotations

import hashlib
import html
import re

import numpy as np
import pandas as pd

from backend.core import config as C

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
_WS_RE = re.compile(r"\s+")
_NEG_RE = re.compile(r"n't\b")


# --------------------------------------------------------------------------- #
# FR-02 – kiểm tra cấu trúc
# --------------------------------------------------------------------------- #
def validate_schema(df: pd.DataFrame) -> dict:
    """Trả về {"ok": bool, "errors": [...], "warnings": [...]}.

    Lỗi (dừng xử lý): thiếu cột bắt buộc; Score không thuộc 1..5 ở mọi dòng;
    Time không phải số nguyên. Cảnh báo: thiếu cột tùy chọn.
    """
    errors, warnings = [], []
    missing = [c for c in C.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append({"code": "MISSING_COLUMN", "columns": missing,
                       "message": f"Thiếu cột bắt buộc: {', '.join(missing)}"})
        return {"ok": False, "errors": errors, "warnings": warnings}
    score = pd.to_numeric(df["Score"], errors="coerce")
    bad_score = int((~score.isin([1, 2, 3, 4, 5])).sum())
    if bad_score == len(df):
        errors.append({"code": "INVALID_SCORE", "message": "Cột Score không có giá trị nguyên 1–5"})
    elif bad_score:
        warnings.append({"code": "INVALID_SCORE_ROWS", "rows": bad_score,
                         "message": f"{bad_score} dòng có Score ngoài 1–5 sẽ bị loại"})
    t = pd.to_numeric(df["Time"], errors="coerce")
    if t.isna().all():
        errors.append({"code": "INVALID_TIME", "message": "Cột Time không phải Unix timestamp"})
    opt_missing = [c for c in C.OPTIONAL_COLUMNS if c not in df.columns]
    if opt_missing:
        warnings.append({"code": "MISSING_OPTIONAL", "columns": opt_missing,
                         "message": "Thiếu cột tùy chọn – một số chức năng sẽ bị ẩn"})
    return {"ok": not errors, "errors": errors, "warnings": warnings}


# --------------------------------------------------------------------------- #
# FR-03 – báo cáo chất lượng
# --------------------------------------------------------------------------- #
def quality_report(df: pd.DataFrame, n_preview: int = 20) -> dict:
    keys = [k for k in C.DEDUP_KEYS if k in df.columns]
    t = pd.to_datetime(pd.to_numeric(df["Time"], errors="coerce"), unit="s")
    rep = {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "n_duplicates": int(df.duplicated(keys).sum()) if keys else 0,
        "missing_by_column": {c: int(v) for c, v in df.isna().sum().items()},
        "time_min": None if t.isna().all() else t.min().strftime("%Y-%m-%d"),
        "time_max": None if t.isna().all() else t.max().strftime("%Y-%m-%d"),
        "preview": df.head(n_preview).drop(columns=["ProfileName"], errors="ignore")
                     .astype(object).where(lambda x: x.notna(), None).to_dict("records"),
    }
    if {"HelpfulnessNumerator", "HelpfulnessDenominator"} <= set(df.columns):
        rep["n_helpfulness_invalid"] = int((df.HelpfulnessNumerator > df.HelpfulnessDenominator).sum())
    return rep


# --------------------------------------------------------------------------- #
# FR-04 – làm sạch
# --------------------------------------------------------------------------- #
def clean_text(s: pd.Series) -> pd.Series:
    """R6: giải mã thực thể HTML, bỏ thẻ HTML và URL, gộp khoảng trắng.

    Giữ nguyên chữ hoa/thường để hiển thị đánh giá mẫu, bằng chứng cho trợ lý AI;
    việc chuyển chữ thường thực hiện trong bước vector hóa (model_preprocess).
    """
    s = s.fillna("").astype(str).map(html.unescape)
    s = s.str.replace(_TAG_RE, " ", regex=True).str.replace(_URL_RE, " ", regex=True)
    return s.str.replace(_WS_RE, " ", regex=True).str.strip()


def model_preprocess(text: str) -> str:
    """Tiền xử lý dùng chung cho huấn luyện và dự đoán (FR-10, FR-14).

    Chữ thường + tách phủ định "n't" → " not" để giữ được bigram "not good".
    """
    return _NEG_RE.sub(" not", text.lower())


def _user_key(u: pd.Series) -> pd.Series:
    return u.fillna("").map(lambda x: hashlib.sha1(x.encode()).hexdigest()[:12])


def clean_reviews(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Áp dụng quy tắc R1–R9, trả về (DataFrame sạch, nhật ký số dòng bị loại)."""
    log = {"n_raw": int(len(raw))}
    df = raw.copy()
    # R1 – Score hợp lệ 1..5
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
    m = df["Score"].isin([1, 2, 3, 4, 5]); log["r1_invalid_score"] = int((~m).sum()); df = df[m]
    # R2 – Time hợp lệ
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    m = df["Time"].notna(); log["r2_invalid_time"] = int((~m).sum()); df = df[m]
    # R3 – nội dung rỗng
    m = df["Text"].fillna("").astype(str).str.strip() != ""
    log["r3_empty_text"] = int((~m).sum()); df = df[m]
    # R4 – Helpfulness bất hợp lệ
    if {"HelpfulnessNumerator", "HelpfulnessDenominator"} <= set(df.columns):
        m = ~(df.HelpfulnessNumerator > df.HelpfulnessDenominator)
        log["r4_helpfulness_invalid"] = int((~m).sum()); df = df[m]
    # R5 – trùng lặp (UserId, Time, Text): giữ bản ghi Id nhỏ nhất, ghi số bản sao
    keys = [k for k in C.DEDUP_KEYS if k in df.columns]
    if "Id" not in df.columns:
        df["Id"] = np.arange(1, len(df) + 1)
    df = df.sort_values("Id")
    # dropna=False: ô UserId trống vẫn được đếm như một giá trị (khớp drop_duplicates), không làm hỏng dup_count
    df["dup_count"] = df.groupby(keys, sort=False, dropna=False)["Id"].transform("size")
    before = len(df); df = df.drop_duplicates(keys, keep="first")
    log["r5_duplicates"] = int(before - len(df))
    # R6 – chuẩn hóa văn bản
    text = clean_text(df["Text"])
    summary = clean_text(df["Summary"]) if "Summary" in df.columns else ""
    # R7 – sau chuẩn hóa còn < 3 từ thì loại
    n_words = text.str.split().str.len()
    m = n_words >= C.MIN_WORDS_PREDICT; log["r7_too_short"] = int((~m).sum())
    dt = pd.to_datetime(df["Time"], unit="s")
    out = pd.DataFrame({
        "review_id": df["Id"].astype("int64"),
        "product_id": df.get("ProductId", pd.Series("UNKNOWN", index=df.index)),
        "user_key": _user_key(df["UserId"]) if "UserId" in df.columns else "",   # R8 – ẩn danh
        "score": df["Score"].astype("int8"),
        "sentiment": df["Score"].map({1: "neg", 2: "neg", 3: "neu", 4: "pos", 5: "pos"}),  # FR-05
        "review_date": dt.dt.strftime("%Y-%m-%d"),
        "year_month": dt.dt.strftime("%Y-%m"),
        "helpful_num": df.get("HelpfulnessNumerator", 0),
        "helpful_den": df.get("HelpfulnessDenominator", 0),
        "summary": summary,
        "text": text,
        "n_words": n_words.astype("int32"),
        "dup_count": df["dup_count"].astype("int16"),
    })[m.values]
    out["helpful_ratio"] = np.where(out.helpful_den > 0, out.helpful_num / out.helpful_den.replace(0, 1), np.nan)
    # R9 – ProfileName không được đưa vào dữ liệu sạch (NFR-05)
    log["n_clean"] = int(len(out))
    return out.reset_index(drop=True), log


# --------------------------------------------------------------------------- #
# Siêu dữ liệu tập dữ liệu (bảng DATASET trong ERD)
# --------------------------------------------------------------------------- #
def dataset_meta(clean: pd.DataFrame) -> dict:
    last_day = pd.Timestamp(clean.review_date.max())
    last_month_complete = last_day == last_day + pd.offsets.MonthEnd(0)
    months = sorted(clean.year_month.unique())
    return {
        "n_reviews": int(len(clean)),
        "n_products": int(clean.product_id.nunique()),
        "n_users": int(clean.user_key.nunique()),
        "date_min": clean.review_date.min(),
        "date_max": clean.review_date.max(),
        "last_full_month": months[-1] if (last_month_complete or len(months) == 1) else months[-2],
        "last_month_complete": bool(last_month_complete),
    }
