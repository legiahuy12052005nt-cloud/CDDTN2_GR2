"""Router analytics – UC-02, UC-05, UC-06: tổng quan, EDA, chủ đề, danh sách sản phẩm (FR-07 – FR-09, FR-18, FR-21)."""
from typing import Literal, Optional

import numpy as np
from fastapi import APIRouter, Depends, Query

from backend.core.deps import require_data
from backend.core.errors import ApiError
from backend.schemas.api import ChartName, ChartResponse, ErrorResponse, Filters, KpiResponse, ProductsResponse, TopicsResponse
from backend.services import eda_service as EDA

router = APIRouter(tags=["Tổng quan & phân tích"])
E409 = {409: {"model": ErrorResponse, "description": "Chưa có dữ liệu (DATASET_NOT_LOADED)"}}


SCORE_SENT = {1: "neg", 2: "neg", 3: "neu", 4: "pos", 5: "pos"}
SENT_VN = {"neg": "Tiêu cực (1–2 sao)", "neu": "Trung tính (3 sao)", "pos": "Tích cực (4–5 sao)"}


def _filters(f: Filters) -> dict:
    """Chuẩn hóa và kiểm tra bộ lọc FR-09 trước khi lọc (dùng chung cho #7 và #8).

    - product_id bỏ khoảng trắng, viết hoa (giống #15, #16, #17) – "b000lqoch0" và "B000LQOCH0" là một;
    - date_from > date_to hoặc số sao không thuộc nhóm cảm xúc đã chọn → 422 VALIDATION_ERROR có thông điệp rõ,
      thay vì trả về 0 đánh giá mà người dùng không biết vì sao.
    """
    d = {k: v for k, v in f.model_dump().items() if v not in (None, "")}
    if d.get("product_id"):
        d["product_id"] = d["product_id"].strip().upper()
        if not d["product_id"]:
            d.pop("product_id")
    if d.get("date_from") and d.get("date_to") and d["date_from"] > d["date_to"]:
        raise ApiError(422, "VALIDATION_ERROR", f"Khoảng thời gian không hợp lệ: từ tháng {d['date_from']} sau đến tháng {d['date_to']}",
                       {"date_from": d["date_from"], "date_to": d["date_to"]})
    if d.get("score") and d.get("sentiment") and SCORE_SENT[int(d["score"])] != d["sentiment"]:
        raise ApiError(422, "VALIDATION_ERROR", f"Bộ lọc mâu thuẫn: {d['score']} sao không thuộc nhóm {SENT_VN[d['sentiment']]}",
                       {"score": d["score"], "sentiment": d["sentiment"]})
    return d


@router.get("/kpi", response_model=KpiResponse, summary="Các chỉ số tổng quan (FR-07)", responses=E409)
def kpi(f: Filters = Depends()):
    st = require_data()
    out = EDA.kpi(st, _filters(f))
    out.update({k: st.meta.get(k) for k in ("date_min", "date_max", "last_full_month")})
    return out


@router.get("/eda/{chart}", response_model=ChartResponse, summary="Dữ liệu cho từng biểu đồ EDA, nhận bộ lọc (FR-08, FR-09)", responses=E409)
def eda(chart: ChartName, f: Filters = Depends()):
    return EDA.chart(require_data(), chart, _filters(f))


@router.get("/topics", response_model=TopicsResponse, summary="Chủ đề phàn nàn và xu hướng (FR-18)",
            responses={**E409, 404: {"model": ErrorResponse, "description": "Không có mã sản phẩm (PRODUCT_NOT_FOUND)"}})
def topics(product_id: Optional[str] = None):
    st = require_data()
    if not st.topics:
        raise ApiError(409, "MODEL_NOT_READY", "Chưa có mô hình chủ đề (dữ liệu quá ít đánh giá tiêu cực)")
    model = f"NMF k={len(st.topics)}"
    n_neg = int((st.df.sentiment == "neg").sum())
    if not product_id:
        return {"meta": st.meta_block(), "model": model, "topics": st.topics, "n_negative": n_neg}
    pid = product_id.strip().upper()
    if not (st.df.product_id == pid).any():              # thống nhất với #15, #16, #17: mã không có → 404
        raise ApiError(404, "PRODUCT_NOT_FOUND", f"Không tìm thấy sản phẩm {pid}")
    ids = st.df.loc[(st.df.product_id == pid) & (st.df.sentiment == "neg"), "review_id"]
    rt = st.review_topics[st.review_topics.review_id.isin(ids) & (st.review_topics.topic_id >= 0)]
    d = st.df.set_index("review_id").loc[rt.review_id] if len(rt) else None
    out = []
    for t in st.topics:
        sub = rt[rt.topic_id == t["topic_id"]].sort_values("topic_weight", ascending=False)
        if sub.empty:
            continue
        smp = [{"review_id": int(i), "score": int(d.loc[i, "score"]), "summary": d.loc[i, "summary"], "text": d.loc[i, "text"][:600],
                "product_id": pid, "date": d.loc[i, "review_date"]} for i in sub.review_id.head(3)]
        out.append({**t, "n_reviews": int(len(sub)), "share": round(len(sub) / len(rt), 4), "samples": smp, "trend": []})
    out.sort(key=lambda t: -t["share"])
    return {"meta": st.meta_block({"product_id": pid}), "model": model, "topics": out, "product_id": pid, "n_negative": int(len(ids))}


SORT_COL = {"n_reviews": "n_reviews", "avg_score": "avg_score", "delta": "delta", "neg_rate": "neg_rate_3m"}


@router.get("/products", response_model=ProductsResponse, summary="Danh sách sản phẩm, mức rủi ro (FR-21)", responses=E409)
def products(q: Optional[str] = Query(None, description="Tìm theo mã sản phẩm (một phần mã)"),
             risk: Optional[Literal["high", "medium", "low", "insufficient"]] = None,
             sort: Literal["risk", "n_reviews", "avg_score", "delta", "neg_rate"] = "risk",
             order: Literal["asc", "desc"] = "desc", page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100),
             min_reviews: int = Query(0, ge=0), forecastable: Optional[bool] = None):
    st = require_data()
    p = st.products
    counts = {k: int(v) for k, v in p.risk_level.value_counts().items()}
    if q:
        p = p[p.product_id.str.contains(q.strip().upper(), regex=False)]
    if risk:
        p = p[p.risk_level == risk]
    if min_reviews:
        p = p[p.n_reviews >= min_reviews]
    if forecastable is not None:
        p = p[p.forecastable == forecastable]
    asc = order == "asc"
    if sort == "risk":
        # cùng mức rủi ro: sản phẩm giảm điểm mạnh nhất lên trước (bài toán “bị đánh giá thấp dần”), rồi tới tỷ lệ tiêu cực
        p = p.sort_values(["risk_rank", "delta", "neg_rate_3m"], ascending=[asc, not asc, asc], na_position="last")
    else:
        p = p.sort_values([SORT_COL[sort], "n_reviews"], ascending=[asc, False], na_position="last")
    total = len(p)
    sub = p.iloc[(page - 1) * page_size: page * page_size]
    items = sub.replace({np.nan: None}).to_dict("records")
    meta = st.meta_block({"q": q, "risk": risk, "sort": sort, "order": order, "min_reviews": min_reviews or None, "forecastable": forecastable})
    return {"meta": meta, "page": {"page": page, "page_size": page_size, "total": total},
            "items": items, "counts": counts, "as_of": st.meta.get("last_full_month"), "backtest": st.risk_backtest}
