"""Router model – UC-03: so sánh mô hình, từ khóa ảnh hưởng, đánh giá lệch (FR-11 – FR-13)."""
from fastapi import APIRouter, Query

from backend.core.deps import require_model
from backend.schemas.api import ErrorResponse, KeywordsResponse, MismatchResponse, ModelMetricsResponse

router = APIRouter(tags=["Mô hình"])
E409 = {409: {"model": ErrorResponse, "description": "Mô hình chưa huấn luyện xong (MODEL_NOT_READY)"}}


@router.get("/model/metrics", response_model=ModelMetricsResponse, summary="Chỉ số so sánh mô hình, ma trận nhầm lẫn (FR-11)", responses=E409)
def metrics():
    st = require_model(); r = st.registry
    return {"meta": st.meta_block(), "split": r["split"], "models": r["models"], "confusion3": r["confusion3"], "confusion5": r["confusion5"],
            "selected": r["selected"], "trained_at": r["trained_at"], "vectorizer": r["vectorizer"], "n_mismatch": r.get("n_mismatch"),
            "time_check": r.get("time_check"), "reference": r.get("reference")}


@router.get("/model/keywords", response_model=KeywordsResponse, summary="Từ khóa làm tăng/giảm số sao (FR-12)", responses=E409)
def keywords(n: int = Query(15, ge=5, le=50)):
    st = require_model(); k = st.registry["keywords"]
    return {"meta": st.meta_block(), "up": k["up"][:n], "down": k["down"][:n]}


@router.get("/reviews/mismatch", response_model=MismatchResponse, summary="Đánh giá có số sao mâu thuẫn nội dung (FR-13)", responses=E409)
def mismatch(threshold: float = Query(0.8, ge=0.5, le=0.99), page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100)):
    st = require_model(); pr = st.predictions
    m = ((pr.score == 5) & (pr.p_neg >= threshold)) | ((pr.score == 1) & (pr.p_pos >= threshold))
    hit = pr[m].assign(conf=lambda x: x[["p_neg", "p_pos"]].max(axis=1)).sort_values("conf", ascending=False)
    total = len(hit)
    sub = hit.iloc[(page - 1) * page_size: page * page_size]
    d = st.df[st.df.review_id.isin(sub.review_id)][["review_id", "product_id", "summary", "text", "review_date"]]
    sub = sub.merge(d, on="review_id", how="left")
    items = [{"review_id": int(r.review_id), "product_id": r.product_id, "score": int(r.score), "pred_sentiment": r.pred_sentiment,
              "p_neg": float(r.p_neg), "p_pos": float(r.p_pos), "summary": r.summary, "text": r.text[:800], "pred_star": int(r.pred_star),
              "review_date": r.review_date} for r in sub.itertuples()]
    return {"meta": st.meta_block({"threshold": threshold}), "page": {"page": page, "page_size": page_size, "total": total}, "items": items}
