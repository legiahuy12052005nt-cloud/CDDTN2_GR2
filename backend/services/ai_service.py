"""AiService – trợ lý AI dùng Gemini (FR-25 – FR-28, NFR-07, NFR-10). Chỉ backend gọi Gemini.

1) insights(): nguyên nhân + giải pháp cho một sản phẩm/chủ đề, mỗi nguyên nhân phải có review_id bằng chứng.
2) chat(): chatbot có “công cụ” (function calling) đọc dữ liệu thật của hệ thống – KPI, sản phẩm rủi ro,
   chủ đề, dự báo, dự đoán một đánh giá, tìm đánh giá – và trả lời được cả câu hỏi kiến thức chung.

Khóa API đặt trong backend/.env (GEMINI_API_KEY) – không đưa lên GitHub, không gửi xuống frontend (NFR-05).
Khóa dạng “AIza…” là khóa Google AI Studio; khóa dạng “AQ.…” là khóa Vertex AI (chế độ express).
Backend tự thử cả hai chế độ và danh sách model dự phòng. Không có khóa hoặc Gemini lỗi → trả lời theo
quy tắc từ dữ liệu hệ thống (suy giảm có kiểm soát – NFR-07) và ghi rõ nguồn trả lời.
"""
from __future__ import annotations

import contextvars
import functools
import json
import os
import re
import time
import unicodedata
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError

from backend.core import config as C
from backend.core.errors import ApiError
from backend.core.state import FILES, STATE, write_json
from backend.services import forecast_service as FS
from backend.services import model_service as MS
from backend.services import topic_service as TS

try:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types
except Exception:  # noqa: BLE001 – thư viện chưa cài: vẫn chạy chế độ quy tắc
    genai = None

import logging  # noqa: E402
logging.getLogger("google_genai.models").setLevel(logging.ERROR)   # cảnh báo AFC của SDK không ảnh hưởng kết quả

_tracker: contextvars.ContextVar[list | None] = contextvars.ContextVar("ai_tracker", default=None)
_ACTIVE: dict = {"mode": None, "model": None, "last_error": None, "last_ok": None}


class AiUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code = code; self.message = message


# =========================================================================== #
# Kết nối Gemini
# =========================================================================== #
def api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")


def configured() -> bool:
    return bool(api_key()) and genai is not None


def status() -> dict:
    return {"configured": configured(), "mode": _ACTIVE["mode"], "model": _ACTIVE["model"],
            "last_error": _ACTIVE["last_error"], "last_ok": _ACTIVE["last_ok"]}


def _modes() -> list[str]:
    m = os.getenv("GEMINI_MODE", "auto").strip().lower()
    if m in ("vertex", "studio"):
        return [m]
    return ["studio", "vertex"] if api_key().startswith("AIza") else ["vertex", "studio"]


def _models() -> list[str]:
    env = os.getenv("GEMINI_MODEL", "").strip()
    return list(dict.fromkeys(([env] if env else []) + C.GEMINI_FALLBACK_MODELS))


_CLIENTS: dict = {}


def _client(mode: str):
    """Giữ tham chiếu client (client bị thu hồi sẽ đóng kết nối HTTP); tạo lại khi đổi khóa/chế độ."""
    base = os.getenv("GEMINI_BASE_URL") or None
    k = (mode, api_key(), base)
    if k not in _CLIENTS:
        opts = {"timeout": C.AI_TIMEOUT_SECONDS * 1000}
        if base:
            opts["base_url"] = base
        if len(_CLIENTS) >= 4:
            _CLIENTS.clear()
        _CLIENTS[k] = (genai.Client(vertexai=True, api_key=api_key(), http_options=types.HttpOptions(**opts)) if mode == "vertex"
                       else genai.Client(api_key=api_key(), http_options=types.HttpOptions(**opts)))
    return _CLIENTS[k]


def _is_key_error(e) -> bool:
    msg = f"{getattr(e, 'message', '')} {getattr(e, 'status', '')} {e}".lower()
    return any(k in msg for k in ["api key", "api_key", "unauthenticated", "permission", "credential", "invalid authentication"])


def _discover(client) -> str | None:
    """Tất cả model trong danh sách đều 404 → hỏi API danh sách model và chọn bản “flash” đầu tiên."""
    try:
        names = [m.name.split("/")[-1] for m in client.models.list()]
    except Exception:  # noqa: BLE001
        return None
    bad = ("image", "tts", "audio", "live", "embedding", "vision", "exp", "learnlm", "thinking")
    flash = [n for n in names if "gemini" in n and "flash" in n and not any(b in n for b in bad)]
    flash.sort(key=lambda n: ("lite" in n, "preview" in n, n), reverse=False)
    return flash[0] if flash else None


def generate(contents, config) -> tuple[object, str]:
    if not configured():
        raise AiUnavailable("NO_KEY", "Chưa cấu hình GEMINI_API_KEY trong backend/.env")
    combos = []
    if _ACTIVE["mode"]:
        combos.append((_ACTIVE["mode"], _ACTIVE["model"]))
    combos += [(md, m) for md in _modes() for m in _models()]
    tried, bad_modes, last, not_found = set(), set(), None, {}
    for mode, model in combos:
        if (mode, model) in tried or mode in bad_modes:
            continue
        tried.add((mode, model))
        try:
            resp = _client(mode).models.generate_content(model=model, contents=contents, config=config)
            _ACTIVE.update(mode=mode, model=model, last_error=None, last_ok=time.strftime("%Y-%m-%d %H:%M:%S"))
            return resp, model
        except Exception as e:  # noqa: BLE001
            last = e
            code = getattr(e, "code", None)
            if genai is not None and isinstance(e, genai_errors.APIError):
                if code in (401, 403) or (code == 400 and _is_key_error(e)):
                    bad_modes.add(mode); continue
                if code == 404:
                    not_found[mode] = not_found.get(mode, 0) + 1; continue
                if code == 429:
                    _ACTIVE["last_error"] = "Gemini báo hết hạn mức (429) – thử lại sau ít phút"
                    raise AiUnavailable("QUOTA", _ACTIVE["last_error"])
                continue
            # lỗi mạng / hết thời gian chờ
            _ACTIVE["last_error"] = f"Không kết nối được Gemini: {type(e).__name__}"
            raise AiUnavailable("NETWORK", _ACTIVE["last_error"])
    for mode, n in not_found.items():          # khóa hợp lệ nhưng không model nào trong danh sách tồn tại
        if mode in bad_modes:
            continue
        try:
            client = _client(mode); model = _discover(client)
            if model:
                resp = client.models.generate_content(model=model, contents=contents, config=config)
                _ACTIVE.update(mode=mode, model=model, last_error=None, last_ok=time.strftime("%Y-%m-%d %H:%M:%S"))
                return resp, model
        except Exception as e:  # noqa: BLE001
            last = e
    if bad_modes and len(bad_modes) == len(set(_modes())):
        msg = "GEMINI_API_KEY không hợp lệ hoặc chưa được cấp quyền (đã thử Google AI Studio và Vertex AI)"
        _ACTIVE["last_error"] = msg
        raise AiUnavailable("BAD_KEY", msg)
    _ACTIVE["last_error"] = f"Gemini lỗi: {str(last)[:200]}"
    raise AiUnavailable("AI_ERROR", _ACTIVE["last_error"])


# =========================================================================== #
# Tiện ích dữ liệu
# =========================================================================== #
def _f(x, nd=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def _require_data():
    if not STATE.dataset_loaded:
        raise ApiError(409, "DATASET_NOT_LOADED", "Chưa có dữ liệu – hãy tải file ở trang Tải dữ liệu")


def _short(text: str, n: int) -> str:
    w = str(text).split()
    return " ".join(w[:n]) + (" …" if len(w) > n else "")


def _product_row(pid: str) -> dict | None:
    if STATE.products is None:
        return None
    r = STATE.products[STATE.products.product_id == pid]
    if r.empty:
        return None
    r = r.iloc[0]
    return {"product_id": pid, "n_reviews": int(r.n_reviews), "avg_score": _f(r.avg_score), "neg_rate": _f(r.neg_rate),
            "first_month": r.first_month, "last_month": r.last_month, "n_active_months": int(r.n_active_months),
            "risk_level": r.risk_level, "reason": r.reason or "", "n_3m": int(r.n_3m), "avg_3m": _f(r.avg_3m),
            "avg_prev_3m": _f(r.avg_prev_3m), "delta_3m": _f(r.delta), "neg_rate_3m": _f(r.neg_rate_3m),
            "forecastable": bool(r.forecastable), "as_of": r.as_of}


def _track(name: str):
    t = _tracker.get()
    if t is not None and name not in t:
        t.append(name)


def _safe(fn):
    @functools.wraps(fn)
    def wrap(*a, **k):
        _track(fn.__name__)
        try:
            if not STATE.dataset_loaded:
                return {"error": "Hệ thống chưa nạp dữ liệu đánh giá nào"}
            return fn(*a, **k)
        except ApiError as e:
            return {"error": e.detail["message"]}
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    return wrap


# =========================================================================== #
# Công cụ cho chatbot (function calling) – đọc dữ liệu thật của hệ thống
# =========================================================================== #
@_safe
def get_overview() -> dict:
    """Tổng quan bộ dữ liệu đánh giá đang nạp trong hệ thống: số đánh giá, số sản phẩm, số người dùng, khoảng thời gian,
    điểm sao trung bình, tỷ lệ đánh giá tiêu cực, chỉ số hài lòng 0-100, phân bố số sao, mô hình dự đoán đang dùng,
    số sản phẩm theo mức rủi ro và dự báo chỉ số hài lòng toàn bộ."""
    d, m = STATE.df, STATE.meta
    avg = float(d.score.mean())
    out = {"n_reviews": len(d), "n_products": int(m["n_products"]), "n_users": int(m["n_users"]),
           "date_min": m["date_min"], "date_max": m["date_max"], "last_full_month": m["last_full_month"],
           "avg_score": _f(avg), "neg_rate": _f((d.sentiment == "neg").mean()), "satisfaction_index": _f(C.satisfaction_index(avg), 1),
           "score_distribution": {int(k): int(v) for k, v in d.score.value_counts().sort_index().items()},
           "clean_log": m.get("clean_log")}
    if STATE.registry:
        s = STATE.registry["selected_metrics"]
        out["model"] = {"selected": STATE.registry["selected"], "f1_macro_3_classes": s["f1_macro3"], "accuracy_5_stars": s["acc5"]}
    if STATE.products is not None:
        out["products_by_risk"] = {k: int(v) for k, v in STATE.products.risk_level.value_counts().items()}
    if STATE.forecast and STATE.forecast.get("forecast"):
        fc = STATE.forecast["forecast"]
        out["forecast_overall"] = {"model": STATE.forecast.get("model"), "next_month": fc[0], "month_6": fc[min(5, len(fc) - 1)]}
    return out


@_safe
def list_risk_products(level: str = "high", limit: int = 10) -> dict:
    """Danh sách sản phẩm theo mức rủi ro (cảnh báo sớm): level là "high" (cao), "medium" (trung bình) hoặc "low".
    Rủi ro cao khi điểm TB 3 tháng gần nhất giảm ≥ 0,5 sao so với 3 tháng trước, hoặc tỷ lệ tiêu cực 3 tháng ≥ 40%.
    Sắp xếp: giảm điểm mạnh nhất trước; signal = "decline" (đang giảm điểm) hoặc "negative" (tiêu cực cao kéo dài, điểm không giảm)."""
    p = STATE.products
    p = p[p.risk_level == level].sort_values(["delta", "neg_rate_3m"], ascending=[True, False], na_position="last").head(max(1, min(int(limit), 30)))
    return {"level": level, "as_of": STATE.meta["last_full_month"], "total_in_level": int((STATE.products.risk_level == level).sum()),
            "items": [{"product_id": r.product_id, "n_reviews": int(r.n_reviews), "avg_3m": _f(r.avg_3m), "avg_prev_3m": _f(r.avg_prev_3m),
                       "delta": _f(r.delta), "neg_rate_3m": _f(r.neg_rate_3m), "reason": r.reason,
                       "signal": getattr(r, "signal", "")} for r in p.itertuples()]}


@_safe
def rank_products(metric: str = "avg_score", ascending: bool = True, min_reviews: int = 20, limit: int = 10) -> dict:
    """Xếp hạng sản phẩm theo một chỉ số: metric là "avg_score" (điểm TB), "neg_rate" (tỷ lệ tiêu cực), "n_reviews"
    (số đánh giá) hoặc "delta" (thay đổi điểm TB 3 tháng). ascending=True để lấy giá trị thấp nhất trước.
    min_reviews lọc sản phẩm có ít nhất bấy nhiêu đánh giá."""
    if metric not in ("avg_score", "neg_rate", "n_reviews", "delta"):
        metric = "avg_score"
    p = STATE.products[STATE.products.n_reviews >= int(min_reviews)].dropna(subset=[metric])
    p = p.sort_values([metric, "n_reviews"], ascending=[bool(ascending), False]).head(max(1, min(int(limit), 30)))
    return {"metric": metric, "ascending": ascending, "min_reviews": min_reviews,
            "items": [{"product_id": r.product_id, "n_reviews": int(r.n_reviews), "avg_score": _f(r.avg_score),
                       "neg_rate": _f(r.neg_rate), "delta_3m": _f(r.delta), "risk_level": r.risk_level} for r in p.itertuples()]}


@_safe
def get_product_info(product_id: str) -> dict:
    """Thông tin chi tiết một sản phẩm theo mã ASIN (ví dụ B007JFMH8M): thống kê, mức rủi ro và lý do, xu hướng 12 tháng
    gần nhất, phân bố chủ đề phàn nàn, 5 đánh giá tiêu cực gần nhất."""
    pid = product_id.strip().upper()
    row = _product_row(pid)
    if row is None:
        return {"error": f"Không tìm thấy sản phẩm {pid}"}
    d = STATE.df[STATE.df.product_id == pid]
    g = FS.monthly(STATE.df, pid).tail(12)
    neg = d[d.score <= 2].sort_values("review_date", ascending=False).head(5)
    row.update({"monthly_last_12": [{"month": r.month, "n": int(r.n), "avg_score": _f(r.avg_score, 2)} for r in g.itertuples()],
                "complaint_topics": TS.product_topics(STATE, pid)[:5],
                "recent_negative_reviews": [{"review_id": int(r.review_id), "date": r.review_date, "score": int(r.score),
                                             "summary": r.summary, "text": _short(r.text, 60)} for r in neg.itertuples()]})
    return row


@_safe
def get_topics(product_id: str = "") -> dict:
    """Các chủ đề phàn nàn tìm được trên đánh giá 1-2 sao (NMF): tên, tỷ trọng, từ khóa, gợi ý hành động.
    Truyền product_id để xem phân bố chủ đề của riêng một sản phẩm."""
    if not STATE.topics:
        return {"error": "Chưa có mô hình chủ đề"}
    if product_id:
        return {"product_id": product_id, "topics": TS.product_topics(STATE, product_id.strip().upper())}
    return {"n_negative_reviews": int((STATE.df.sentiment == "neg").sum()),
            "topics": [{"topic_id": t["topic_id"], "name": t["name"], "share": t["share"], "n_reviews": t["n_reviews"],
                        "keywords": t["keywords"][:6], "suggestion": t["suggestion"],
                        "share_last_month": (t["trend"][-1]["share"] if t["trend"] else None)} for t in STATE.topics]}


@_safe
def get_forecast(product_id: str = "", months: int = 6) -> dict:
    """Dự báo chỉ số hài lòng (0-100) cho 3, 6 hoặc 12 tháng tới, kèm khoảng tin cậy 95% và sai số kiểm tra lùi (backtest).
    Để trống product_id để dự báo toàn bộ; sản phẩm cần ≥ 36 tháng có đánh giá mới dự báo được."""
    months = 3 if int(months) <= 3 else (6 if int(months) <= 6 else 12)
    r = FS.forecast(STATE, product_id.strip().upper() or None, months)
    return {"scope": r["scope"], "product_id": r.get("product_id"), "eligible": r["eligible"], "message": r.get("message"),
            "model": r.get("model"), "last_history": r["history"][-3:], "forecast": r["forecast"], "backtest": r.get("backtest")}


@_safe
def get_monthly_trend(product_id: str = "", last_n_months: int = 12) -> dict:
    """Chuỗi theo tháng: số đánh giá, điểm TB, tỷ lệ tiêu cực, chỉ số hài lòng. Để trống product_id để lấy toàn bộ."""
    g = FS.monthly(STATE.df, product_id.strip().upper() or None)
    g = g[g.month <= STATE.meta["last_full_month"]].tail(max(1, min(int(last_n_months), 60)))
    return {"product_id": product_id or None,
            "series": [{"month": r.month, "n": int(r.n), "avg_score": _f(r.avg_score, 2), "neg_rate": _f(r.neg_rate),
                        "sat_index": _f(r.sat_index, 1)} for r in g.itertuples()]}


@_safe
def predict_review(text: str) -> dict:
    """Dùng mô hình học máy của hệ thống (huấn luyện trên dữ liệu đã làm sạch) để dự đoán số sao 1-5, cảm xúc,
    chỉ số hài lòng và các từ ảnh hưởng của một đánh giá (văn bản tiếng Anh cho kết quả chính xác nhất)."""
    if not STATE.model_ready:
        return {"error": "Mô hình chưa huấn luyện xong"}
    if len(text.split()) < C.MIN_WORDS_PREDICT:                     # cùng điều kiện với API #14 (FR-14)
        return {"error": f"Nội dung cần tối thiểu {C.MIN_WORDS_PREDICT} từ để dự đoán"}
    return predict_full(text, None)


@_safe
def search_reviews(keyword: str, product_id: str = "", sentiment: str = "", limit: int = 5) -> dict:
    """Tìm đánh giá có chứa từ khóa (tiếng Anh, ví dụ "stale", "expired", "too sweet"). Có thể lọc theo product_id và
    sentiment ("neg", "neu", "pos"). Trả về số kết quả và vài đánh giá mới nhất."""
    d = STATE.df
    if product_id:
        d = d[d.product_id == product_id.strip().upper()]
    if sentiment in ("neg", "neu", "pos"):
        d = d[d.sentiment == sentiment]
    kw = keyword.strip().lower()
    m = d.text.str.lower().str.contains(kw, regex=False) | d.summary.str.lower().str.contains(kw, regex=False)
    hit = d[m]
    top = hit.sort_values("review_date", ascending=False).head(max(1, min(int(limit), 10)))
    return {"keyword": keyword, "n_matches": int(len(hit)), "share_negative": _f((hit.sentiment == "neg").mean()) if len(hit) else None,
            "avg_score": _f(hit.score.mean()) if len(hit) else None,
            "items": [{"review_id": int(r.review_id), "product_id": r.product_id, "date": r.review_date, "score": int(r.score),
                       "summary": r.summary, "text": _short(r.text, 50)} for r in top.itertuples()]}


@_safe
def get_model_info() -> dict:
    """Thông tin mô hình dự đoán: các mô hình đã so sánh (Logistic Regression, Naive Bayes, Linear SVM, đường cơ sở),
    chỉ số F1-macro, độ chính xác, mô hình được chọn, cách chia dữ liệu và từ khóa làm tăng/giảm số sao."""
    if not STATE.registry:
        return {"error": "Mô hình chưa huấn luyện xong"}
    r = STATE.registry
    return {"selected": r["selected"], "trained_at": r["trained_at"], "split": r["split"],
            "models": [{k: m[k] for k in ("model", "params", "f1_macro3", "f1_neg", "f1_neu", "f1_pos", "acc5", "mae")} for m in r["models"]],
            "keywords_up": [k["term"] for k in r["keywords"]["up"][:10]], "keywords_down": [k["term"] for k in r["keywords"]["down"][:10]],
            "n_mismatch_test": r.get("n_mismatch")}


TOOLS = [get_overview, list_risk_products, rank_products, get_product_info, get_topics, get_forecast,
         get_monthly_trend, predict_review, search_reviews, get_model_info]
TOOL_LABEL = {"get_overview": "KPI tổng quan", "list_risk_products": "Bảng cảnh báo sản phẩm", "rank_products": "Xếp hạng sản phẩm",
              "get_product_info": "Chi tiết sản phẩm", "get_topics": "Chủ đề phàn nàn", "get_forecast": "Dự báo chỉ số hài lòng",
              "get_monthly_trend": "Chuỗi theo tháng", "predict_review": "Mô hình dự đoán", "search_reviews": "Tìm kiếm đánh giá",
              "get_model_info": "Chỉ số mô hình"}


# =========================================================================== #
# Dự đoán đầy đủ (dùng chung cho API /predict và chatbot)
# =========================================================================== #
def predict_full(text: str, summary: str | None) -> dict:
    out = MS.predict(STATE.model, text, summary)
    vec = STATE.model["vectorizer"]
    # tách từ đúng như lúc vector hóa (chữ thường, n't → not); tử số và mẫu số cùng một danh sách từ nên tỷ lệ ≤ 1
    words = vec.build_tokenizer()(vec.build_preprocessor()((summary or "") + " . " + text))
    known = sum(1 for w in words if w in vec.vocabulary_)
    ratio = known / max(len(words), 1)
    out["known_token_ratio"] = round(ratio, 3)
    notes = []
    if ratio < 0.35:
        notes.append("Mô hình học từ đánh giá tiếng Anh; nội dung này có ít từ mô hình đã biết "
                     f"({ratio:.0%}) nên kết quả có thể kém chính xác – hãy nhập đánh giá bằng tiếng Anh.")
    star_sent = MS.SENT_CODE[MS.SENT[out["pred_star"]]]
    if star_sent != out["sentiment"]:
        # QĐ-03: số sao = mức có xác suất cao nhất; cảm xúc = nhóm có tổng xác suất cao nhất (cùng cách đánh giá ở mục 5.2)
        p = out["proba"][str(out["pred_star"])]; q = out["sentiment_proba"][out["sentiment"]]
        notes.append(f"Mức {out['pred_star']} sao có xác suất riêng cao nhất ({p:.0%}) nhưng tổng xác suất nhóm "
                     f"{SENT_VN[out['sentiment']].lower()} cao hơn ({q:.0%}): nội dung vừa khen vừa chê, kết quả không chắc chắn – "
                     "xem phân bố xác suất 5 mức sao.")
    out["note"] = " ".join(notes) or None
    out["topic"] = None; out["suggestion"] = None
    if out["sentiment"] == "neg" and STATE.topic_model is not None and STATE.topics:
        t = TS.transform(STATE.topic_model, STATE.topics, (summary or "") + " . " + text)
        if t:
            out["topic"] = {"topic_id": t["topic_id"], "name": t["name"], "weight": t["weight"]}
            out["suggestion"] = t["suggestion"]
    reg = STATE.registry or {}
    out["model_info"] = {"model": reg.get("selected"), "f1_macro3": (reg.get("selected_metrics") or {}).get("f1_macro3"),
                         "n_train": (reg.get("split") or {}).get("train"), "dataset_version": STATE.version}
    return out


# =========================================================================== #
# Chatbot
# =========================================================================== #
CHAT_SYSTEM = """Bạn là “Trợ lý FoodReview” – trợ lý AI của hệ thống FoodReview Insight: ứng dụng phân tích và dự báo mức độ hài lòng
của khách hàng từ dữ liệu đánh giá thực phẩm trên Amazon (bộ Amazon Fine Food Reviews), giúp người bán phát hiện sớm vấn đề
người mua phản ánh và sản phẩm đang bị đánh giá thấp dần.

Cách làm việc:
1. Câu hỏi về dữ liệu, sản phẩm, chủ đề phàn nàn, cảnh báo, dự báo, mô hình của hệ thống → LUÔN gọi công cụ để lấy số liệu thật,
   có thể gọi nhiều công cụ; tuyệt đối không bịa số liệu. Công cụ báo lỗi/không có dữ liệu thì nói rõ điều đó.
2. Người dùng đưa một câu đánh giá và muốn biết số sao/cảm xúc → gọi predict_review (dịch sang tiếng Anh trước nếu đánh giá viết
   bằng tiếng Việt, vì mô hình học trên tiếng Anh, và nói rõ đã dịch).
3. Câu hỏi ngoài hệ thống (kiến thức chung, thực phẩm, kinh doanh, marketing, học máy, thống kê, lập trình, …) → trả lời như một trợ lý AI
   đa năng bằng kiến thức của bạn; khi hữu ích thì liên hệ với dữ liệu của hệ thống.
4. Trả lời bằng tiếng Việt (trừ khi người dùng viết bằng ngôn ngữ khác), ngắn gọn, đi thẳng vào ý; dùng Markdown: gạch đầu dòng,
   **in đậm** số liệu chính, bảng nhỏ khi so sánh. Số thập phân dùng dấu phẩy. Trích đánh giá gốc tiếng Anh thì kèm ý dịch ngắn.
5. Khi đưa ra dự đoán hoặc khuyến nghị, nêu căn cứ (số liệu, mô hình) và mức độ chắc chắn.

Thuật ngữ: chỉ số hài lòng = (điểm sao TB − 1) / 4 × 100; tiêu cực = 1–2 sao, trung tính = 3 sao, tích cực = 4–5 sao.
Rủi ro cao: điểm TB 3 tháng gần nhất giảm ≥ 0,5 sao hoặc tỷ lệ tiêu cực 3 tháng ≥ 40%; trung bình: giảm ≥ 0,25 sao hoặc ≥ 25%."""


def _context_text(context: dict | None) -> str:
    parts = []
    if STATE.dataset_loaded:
        m = STATE.meta
        parts.append(f"Dữ liệu đang nạp: {_vn(m['n_reviews'], 0)} đánh giá, {_vn(m['n_products'], 0)} sản phẩm, từ {m['date_min']} đến {m['date_max']}"
                     f" (tháng trọn vẹn cuối: {m['last_full_month']}), phiên bản {STATE.version}.")
    else:
        parts.append("Hệ thống chưa nạp dữ liệu đánh giá.")
    if context:
        if context.get("page"):
            parts.append(f"Người dùng đang xem màn hình: {context['page']}.")
        if context.get("product_id"):
            parts.append(f"Sản phẩm đang chọn: {context['product_id']} (hiểu “sản phẩm này” là sản phẩm này).")
        if context.get("topic_id") not in (None, ""):
            parts.append(f"Chủ đề đang chọn: topic_id = {context['topic_id']}.")
    parts.append(f"Hôm nay: {time.strftime('%d/%m/%Y')}.")
    return "\n".join(parts)


def chat(message: str, history: list[dict], context: dict | None = None) -> dict:
    t0 = time.time()
    tracker: list = []
    token = _tracker.set(tracker)
    try:
        if configured():
            try:
                contents = [types.Content(role="user" if h["role"] == "user" else "model", parts=[types.Part(text=h["content"])])
                            for h in history[-10:]]
                contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
                cfg = types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM + "\n\nNGỮ CẢNH:\n" + _context_text(context),
                    tools=TOOLS, temperature=0.4,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=8))
                resp, model = generate(contents, cfg)
                text = (resp.text or "").strip()
                if not text:
                    text = "Mình chưa tạo được câu trả lời cho câu hỏi này, bạn thử diễn đạt lại nhé."
                return {"answer": text, "data_used": [TOOL_LABEL.get(t, t) for t in tracker], "cached": False,
                        "source": "gemini", "model": model, "latency_ms": round((time.time() - t0) * 1000)}
            except AiUnavailable as e:
                note = e.message
        else:
            note = "Chưa cấu hình GEMINI_API_KEY nên trợ lý đang trả lời theo quy tắc từ dữ liệu hệ thống"
        ans = _rule_chat(message, context)
        return {"answer": ans + f"\n\n> _{note}._", "data_used": [TOOL_LABEL.get(t, t) for t in tracker], "cached": False,
                "source": "rule", "model": None, "latency_ms": round((time.time() - t0) * 1000)}
    finally:
        _tracker.reset(token)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _vn(x, nd=2):
    return "–" if x is None else f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x):
    return "–" if x is None else f"{x * 100:.1f}%".replace(".", ",")


RISK_VN = {"high": "Cao", "medium": "Trung bình", "low": "Thấp", "insufficient": "Chưa đủ dữ liệu"}
SENT_VN = {"neg": "Tiêu cực", "neu": "Trung tính", "pos": "Tích cực"}


def _rule_chat(message: str, context: dict | None) -> str:
    q = _norm(message)
    pid = re.search(r"\b(B[0-9A-Z]{9}|[0-9]{9}[0-9X])\b", message.upper())
    pid = pid.group(1) if pid else None
    if not pid and context and context.get("product_id") and any(k in q for k in ["san pham nay", "sp nay", "this product"]):
        pid = context["product_id"]
    quoted = re.search(r"[\"“'](.{8,})[\"”']", message)
    if any(k in q for k in ["du doan", "predict", "cham sao", "may sao"]) and (quoted or ":" in message):
        text = quoted.group(1) if quoted else message.split(":", 1)[1]
        r = predict_review(text.strip())
        if "error" in r:
            return r["error"]
        top = ", ".join(f"`{t['token']}` ({'+' if t['weight'] > 0 else ''}{_vn(t['weight'])})" for t in r["tokens"][:6])
        s = (f"**Dự đoán:** {r['pred_star']} sao – {SENT_VN[r['sentiment']]} (chỉ số hài lòng **{_vn(r['satisfaction_index'], 1)}**/100).\n\n"
             f"- Xác suất theo sao: " + ", ".join(f"{k}★ {_pct(v)}" for k, v in r["proba"].items()) + f"\n- Từ ảnh hưởng: {top}")
        if r.get("topic"):
            s += f"\n- Chủ đề phàn nàn gần nhất: **{r['topic']['name']}** – gợi ý: {r['suggestion']}"
        if r.get("note"):
            s += f"\n- Lưu ý: {r['note']}"
        return s
    term = re.search(r"[\"“‘']([^\"”’']{2,60})[\"”’']", message)
    if term and any(k in q for k in ["nhac toi", "nhac den", "co tu", "chua tu", "tim danh gia", "tim kiem", "search", "mention"]):
        r = search_reviews(term.group(1), pid or "")
        if "error" in r:
            return r["error"]
        if not r["n_matches"]:
            return f"Không có đánh giá nào chứa “{r['keyword']}”" + (f" của sản phẩm {pid}." if pid else ".")
        rows = "\n".join(f"- {i['date']} · {i['score']}★ · {i['product_id']}: “{i['summary']}”" for i in r["items"][:5])
        return (f"Có **{_vn(r['n_matches'], 0)} đánh giá** chứa “{r['keyword']}”" + (f" của sản phẩm {pid}" if pid else "") +
                f": điểm TB **{_vn(r['avg_score'])}**, {_pct(r['share_negative'])} là đánh giá tiêu cực.\n\nMới nhất:\n" + rows)
    if pid:
        r = get_product_info(pid)
        if "error" in r:
            return r["error"]
        s = (f"**Sản phẩm {pid}** – {r['n_reviews']} đánh giá, điểm TB **{_vn(r['avg_score'])}**, tỷ lệ tiêu cực {_pct(r['neg_rate'])}.\n\n"
             f"- Mức rủi ro ({r['as_of']}): **{RISK_VN[r['risk_level']]}**" + (f" – {r['reason']}" if r["reason"] else "") +
             f"\n- 3 tháng gần nhất: {r['n_3m']} đánh giá, điểm TB {_vn(r['avg_3m'])} (3 tháng trước {_vn(r['avg_prev_3m'])})")
        if r["complaint_topics"]:
            s += "\n- Chủ đề phàn nàn chính: " + "; ".join(f"{t['name']} ({_pct(t['share'])})" for t in r["complaint_topics"][:3])
        if r["recent_negative_reviews"]:
            x = r["recent_negative_reviews"][0]
            s += f"\n- Đánh giá tiêu cực gần nhất ({x['date']}, {x['score']}★): “{x['summary']}”"
        return s
    if any(k in q for k in ["rui ro", "canh bao", "giam dan", "dang giam", "nguy co", "risk"]):
        r = list_risk_products("high", 8)
        if "error" in r:
            return r["error"]
        # danh sách thay cho bảng 4 cột: khung chat hẹp, cột “Lý do” dài sẽ bị bóp thành từng chữ
        def _row(i):
            d = i["delta"]
            chg = "–" if d is None else (("+" if d > 0 else "") + _vn(d))
            tag = "đang giảm điểm" if i.get("signal") == "decline" else "tiêu cực cao kéo dài, điểm không giảm"
            return f"- **{i['product_id']}** – điểm TB 3 tháng {_vn(i['avg_prev_3m'])} → {_vn(i['avg_3m'])} sao ({chg}), tiêu cực {_pct(i['neg_rate_3m'])} · _{tag}_"
        rows = "\n".join(_row(i) for i in r["items"])
        return (f"Có **{r['total_in_level']} sản phẩm rủi ro cao** (tính đến {r['as_of']}). Nhóm cần xử lý trước, giảm điểm mạnh nhất lên đầu:\n\n" + rows)
    if any(k in q for k in ["chu de", "phan nan", "van de", "complain", "nguyen nhan"]):
        r = get_topics()
        if "error" in r:
            return r["error"]
        rows = "\n".join(f"{i + 1}. **{t['name']}** – {_pct(t['share'])} đánh giá tiêu cực; từ khóa: {', '.join(t['keywords'][:4])}"
                         for i, t in enumerate(sorted(r["topics"], key=lambda t: -t["share"])))
        return f"Trên {_vn(r['n_negative_reviews'], 0)} đánh giá tiêu cực, hệ thống tìm được các chủ đề phàn nàn:\n\n" + rows
    if any(k in q for k in ["du bao", "tuong lai", "thang toi", "sap toi", "forecast"]):
        r = get_forecast("", 6)
        if "error" in r or not r["eligible"]:
            return r.get("error") or r.get("message")
        rows = "\n".join(f"| {p['month']} | {_vn(p['sat_index'], 1)} | {_vn(p['lo'], 1)} – {_vn(p['hi'], 1)} |" for p in r["forecast"])
        bt = r.get("backtest") or {}
        return (f"Dự báo chỉ số hài lòng toàn bộ 6 tháng tới ({r['model']}):\n\n| Tháng | Chỉ số | Khoảng tin cậy 95% |\n|---|---|---|\n" + rows +
                (f"\n\nKiểm tra lùi 12 tháng: MAE **{_vn(bt.get('mae_model'))}** điểm, so với {_vn(bt.get('mae_naive'))} của mô hình ngây thơ." if bt else ""))
    if any(k in q for k in ["mo hinh", "f1", "do chinh xac", "accuracy", "model"]):
        r = get_model_info()
        if "error" in r:
            return r["error"]
        rows = "\n".join(f"| {m['model']} | {_vn(m['f1_macro3'], 3)} | {_vn(m['acc5'], 3)} | {_vn(m['mae'], 3)} |" for m in r["models"])
        return (f"Mô hình đang dùng: **{r['selected']}** (huấn luyện {r['trained_at']} trên {_vn(r['split']['train'], 0)} đánh giá đã làm sạch).\n\n" +
                "| Mô hình | F1-macro 3 lớp | Accuracy 5 sao | MAE |\n|---|---|---|---|\n" + rows)
    if any(k in q for k in ["tong quan", "bao nhieu", "kpi", "diem trung binh", "hai long", "overview", "du lieu"]):
        r = get_overview()
        if "error" in r:
            return r["error"]
        return (f"Bộ dữ liệu có **{_vn(r['n_reviews'], 0)} đánh giá** của {_vn(r['n_products'], 0)} sản phẩm, {_vn(r['n_users'], 0)} người dùng "
                f"({r['date_min']} → {r['date_max']}).\n\n" +
                f"- Điểm TB **{_vn(r['avg_score'])}**/5 – chỉ số hài lòng **{_vn(r['satisfaction_index'], 1)}**/100\n"
                f"- Tỷ lệ tiêu cực {_pct(r['neg_rate'])}\n"
                f"- Sản phẩm rủi ro cao: {r.get('products_by_risk', {}).get('high', 0)}")
    return ("Mình có thể trả lời từ dữ liệu hệ thống, ví dụ:\n\n- “Tổng quan dữ liệu thế nào?”\n- “Những sản phẩm nào đang rủi ro cao?”\n"
            "- “Khách phàn nàn về chủ đề gì nhiều nhất?”\n- “Dự báo chỉ số hài lòng 6 tháng tới”\n- “Sản phẩm B007JFMH8M thế nào?”\n"
            "- “Dự đoán: \"The coffee was stale and tasted burnt\"”\n\nCâu hỏi kiến thức chung (ngoài dữ liệu) cần kết nối Gemini.")


# =========================================================================== #
# Phân tích nguyên nhân – giải pháp (FR-26 – FR-28)
# =========================================================================== #
Level = Literal["cao", "trung bình", "thấp"]


class _NN(BaseModel):
    ten: str
    mo_ta: str
    muc_do: Level
    id_bang_chung: list[int]


class _GP(BaseModel):
    nguyen_nhan: int
    hanh_dong: str
    uu_tien: Level
    chi_so_theo_doi: str


class _Out(BaseModel):
    nguyen_nhan: list[_NN]
    giai_phap: list[_GP]


INSIGHT_PROMPT = """Bạn là chuyên gia phân tích trải nghiệm khách hàng ngành thực phẩm. Trả lời bằng tiếng Việt.
DỮ LIỆU: {stats}
ĐÁNH GIÁ (mỗi dòng: [review_id] số sao | tiêu đề | nội dung):
{reviews}
YÊU CẦU:
1. Nêu tối đa 5 nguyên nhân khiến khách không hài lòng, sắp theo mức nghiêm trọng.
2. MỖI nguyên nhân phải trích ≥ 1 review_id CÓ TRONG danh sách trên làm bằng chứng; không suy đoán ngoài dữ liệu.
3. Với mỗi nguyên nhân, đề xuất 1 hành động cụ thể, mức ưu tiên và 1 chỉ số theo dõi (giai_phap.nguyen_nhan là số thứ tự nguyên nhân, bắt đầu từ 1).
4. Chỉ trả về JSON đúng lược đồ: nguyen_nhan[{{ten, mo_ta, muc_do, id_bang_chung[]}}], giai_phap[{{nguyen_nhan, hanh_dong, uu_tien, chi_so_theo_doi}}]; không thêm văn bản khác."""


def _load_cache() -> dict:
    try:
        return json.loads(FILES["ai_cache"].read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_cache(c: dict) -> None:
    write_json(FILES["ai_cache"], c)


def _recent_cutoff() -> str:
    """Tháng bắt đầu cửa sổ “12 tháng gần nhất” (tính đến tháng mới nhất có dữ liệu)."""
    last = pd.Period(str(STATE.meta.get("date_max") or STATE.df.year_month.max())[:7], "M")
    return str(last - (C.AI_RECENT_MONTHS - 1))


def _insight_context(scope: str, sid: str) -> dict:
    """Chọn ≤ 30 đánh giá tiêu biểu gửi Gemini (mục 5.6 tài liệu thiết kế):
    ưu tiên đánh giá trong 12 tháng gần nhất, thiếu thì bổ sung từ lịch sử; sản phẩm sắp theo (helpful_num, ngày),
    chủ đề sắp theo (trọng số chủ đề, helpful_num); mỗi đánh giá cắt còn 120 từ; không gửi user_key."""
    d = STATE.df
    cutoff = _recent_cutoff()
    if scope == "product":
        pid = sid.strip().upper(); row = _product_row(pid)
        if row is None:
            raise ApiError(404, "PRODUCT_NOT_FOUND", f"Không tìm thấy sản phẩm {pid}")
        p = d[d.product_id == pid]
        rv = p[p.score <= 2]
        if len(rv) < 5:                                   # quá ít đánh giá 1–2 sao: thêm đánh giá 3 sao
            rv = p[p.score <= 3]
        rv = rv.assign(_recent=rv.year_month >= cutoff, _neg=rv.score <= 2)
        rv = rv.sort_values(["_recent", "_neg", "helpful_num", "review_date"], ascending=[False, False, False, False])
        rv = rv.head(C.AI_MAX_REVIEWS)
        topics = TS.product_topics(STATE, pid)[:4]
        d3 = row["delta_3m"]
        stats = (f"sản phẩm {pid}: {row['n_reviews']} đánh giá, điểm TB {_vn(row['avg_score'])}, tỷ lệ tiêu cực {_pct(row['neg_rate'])}; "
                 f"3 tháng gần nhất (đến {row['as_of']}): {row['n_3m']} đánh giá, điểm TB {_vn(row['avg_3m'])}"
                 f"{'' if d3 is None else f', thay đổi {d3:+.2f} sao so với 3 tháng trước'.replace('.', ',')}; "
                 f"mức rủi ro {RISK_VN[row['risk_level']]}; chủ đề chính: " + (", ".join(f"{t['name']} {_pct(t['share'])}" for t in topics) or "–"))
        title = f"Sản phẩm {pid}"
        topic_ids = {}
    else:
        if not STATE.topics:
            raise ApiError(409, "MODEL_NOT_READY", "Chưa có mô hình chủ đề")
        try:
            i = int(sid)
        except ValueError:
            i = -1
        if not 0 <= i < len(STATE.topics):
            raise ApiError(404, "TOPIC_NOT_FOUND", f"Không có chủ đề {sid}")
        t = STATE.topics[i]
        rt = STATE.review_topics[STATE.review_topics.topic_id == t["topic_id"]]
        rv = d[d.review_id.isin(rt.review_id) & (d.n_words >= 15)].merge(rt[["review_id", "topic_weight"]], on="review_id")
        rv = rv.assign(_recent=rv.year_month >= cutoff)
        rv = rv.sort_values(["_recent", "topic_weight", "helpful_num"], ascending=[False, False, False])
        rv = rv.head(C.AI_MAX_REVIEWS)
        stats = (f"chủ đề phàn nàn “{t['name']}”: {_vn(t['n_reviews'], 0)} đánh giá tiêu cực ({_pct(t['share'])} tổng đánh giá 1–2 sao); "
                 f"từ khóa: {', '.join(t['keywords'])}")
        title = t["name"]
        topic_ids = {"topic": t}
    reviews = [{"review_id": int(r.review_id), "score": int(r.score), "summary": r.summary, "date": r.review_date,
                "product_id": r.product_id, "text": _short(r.text, C.AI_REVIEW_MAX_WORDS)} for r in rv.itertuples()]
    return {"scope": scope, "id": sid, "title": title, "stats": stats, "reviews": reviews, **topic_ids}


def _evidence(ids: list[int], by_id: dict) -> list[dict]:
    return [{"review_id": i, "score": by_id[i]["score"], "summary": by_id[i]["summary"], "text": by_id[i]["text"],
             "date": by_id[i]["date"], "product_id": by_id[i]["product_id"]} for i in ids if i in by_id]


def _gemini_insight(ctx: dict) -> dict:
    by_id = {r["review_id"]: r for r in ctx["reviews"]}
    lines = "\n".join(f"[{r['review_id']}] {r['score']} | {r['summary']} | {r['text']}" for r in ctx["reviews"])
    prompt = INSIGHT_PROMPT.format(stats=ctx["stats"], reviews=lines)
    cfg = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json", response_schema=_Out)
    out, model = None, None
    for attempt in range(2):
        resp, model = generate(prompt if attempt == 0 else prompt + "\nLƯU Ý: lần trước trả về sai lược đồ JSON, hãy trả đúng lược đồ.", cfg)
        try:
            out = _Out.model_validate_json(_strip_json(resp.text or ""))
            break
        except ValidationError:
            out = None
    if out is None:
        raise ApiError(502, "AI_BAD_OUTPUT", "Gemini trả về sai lược đồ JSON sau 2 lần gọi")
    causes, keep_map, dropped = [], {}, 0
    for i, c in enumerate(out.nguyen_nhan[:5]):
        ids = [int(x) for x in c.id_bang_chung if int(x) in by_id]
        if not ids:
            dropped += 1; continue
        keep_map[i + 1] = len(causes)
        causes.append({"title": c.ten, "description": c.mo_ta, "severity": c.muc_do, "evidence_ids": ids, "evidence": _evidence(ids, by_id)})
    sols = [{"cause_index": keep_map[s.nguyen_nhan], "action": s.hanh_dong, "priority": s.uu_tien, "kpi": s.chi_so_theo_doi}
            for s in out.giai_phap if s.nguyen_nhan in keep_map]
    return {"model": model, "source": "gemini", "causes": causes, "solutions": sols, "dropped_causes": dropped, "note": None}


def _strip_json(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(json)?", "", s).rstrip("`").strip()
    return s


def _rule_insight(ctx: dict, note: str) -> dict:
    """Không có Gemini: nguyên nhân = chủ đề NMF chiếm tỷ trọng cao trong các đánh giá bằng chứng; giải pháp = bảng quy tắc FR-16."""
    by_id = {r["review_id"]: r for r in ctx["reviews"]}
    causes, sols = [], []
    if STATE.topic_model is not None and ctx["reviews"]:
        groups: dict[int, list] = {}
        for r in ctx["reviews"]:
            t = TS.transform(STATE.topic_model, STATE.topics, f"{r['summary']} . {r['text']}")
            if t:
                groups.setdefault(t["topic_id"], []).append((t["weight"], r["review_id"]))
        order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        if ctx["scope"] == "topic":
            order = order[:1] if order else []
        n = max(len(ctx["reviews"]), 1)
        # sản phẩm có < 5 đánh giá 1–2 sao thì đã gửi kèm đánh giá 3 sao (mục 5.6): gọi đúng tên, không gọi chung là “tiêu cực”
        label = "đánh giá tiêu cực" if all(r["score"] <= 2 for r in ctx["reviews"]) else "đánh giá 1–3 sao"
        for tid, items in order[:4]:
            t = STATE.topics[tid]; share = len(items) / n
            ids = [i for _, i in sorted(items, reverse=True)[:3]]
            n_neg = sum(by_id[i]["score"] <= 2 for _, i in items)
            sev = "cao" if share >= 0.35 else ("trung bình" if share >= 0.15 else "thấp")
            if n_neg == 0:                                  # chỉ có đánh giá 3 sao: không xếp mức nghiêm trọng cao
                sev = "thấp"
            causes.append({"title": t["name"], "description": f"{len(items)}/{n} {label} được gửi phân tích thuộc chủ đề này"
                           f"{'' if label == 'đánh giá tiêu cực' else f' ({n_neg} đánh giá 1–2 sao)'} "
                           f"(từ khóa: {', '.join(t['keywords'][:5])}).", "severity": sev, "evidence_ids": ids, "evidence": _evidence(ids, by_id)})
            sols.append({"cause_index": len(causes) - 1, "action": t["suggestion"], "priority": sev,
                         "kpi": "Tỷ lệ đánh giá 1–2 sao thuộc chủ đề này theo tháng; điểm TB 3 tháng"})
    return {"model": "quy tắc (chủ đề NMF + bảng gợi ý FR-16)", "source": "rule", "causes": causes, "solutions": sols,
            "dropped_causes": 0, "note": note}


def insights(scope: str, sid: str, refresh: bool) -> dict:
    _require_data()
    sid = sid.strip().upper() if scope == "product" else sid.strip()   # “b00507a02q” và “B00507A02Q” dùng chung một mục lưu đệm
    key = f"{scope}|{sid}|{STATE.version}"
    cache = _load_cache()
    if not refresh and key in cache:
        return {**cache[key], "cached": True}
    ctx = _insight_context(scope, sid)
    t0 = time.time()
    if configured():
        try:
            res = _gemini_insight(ctx)
        except AiUnavailable as e:
            if key in cache:
                return {**cache[key], "cached": True, "note": f"{e.message} – đang hiển thị kết quả đã lưu"}
            res = _rule_insight(ctx, f"{e.message} – đang dùng phân tích theo quy tắc")
    else:
        res = _rule_insight(ctx, "Chưa cấu hình GEMINI_API_KEY – đang dùng phân tích theo quy tắc từ mô hình chủ đề")
    out = {"scope": scope, "id": sid, "title": ctx["title"], "stats": ctx["stats"], "n_reviews_sent": len(ctx["reviews"]),
           "cached": False, "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "latency_ms": round((time.time() - t0) * 1000), **res}
    if res["source"] == "gemini":
        cache[key] = out; _save_cache(cache)
    return out
