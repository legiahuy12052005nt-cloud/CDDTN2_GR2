"""Router predict – UC-04: tự nhập đánh giá để dự đoán (FR-14 – FR-16)."""
import time

from fastapi import APIRouter

from backend.core import config as C
from backend.core.deps import require_model
from backend.core.errors import ApiError
from backend.schemas.api import ErrorResponse, PredictRequest, PredictResponse
from backend.services import ai_service as AI

router = APIRouter(tags=["Dự đoán"])


@router.post("/predict", response_model=PredictResponse, summary="Dự đoán số sao, cảm xúc, chỉ số hài lòng của một đánh giá",
             description="Dùng mô hình đã huấn luyện trên dữ liệu đã làm sạch, chuẩn hóa của phiên hiện tại; văn bản nhập vào "
                         "được chuẩn hóa giống dữ liệu huấn luyện (chữ thường, n't → not, TF-IDF 1–2-gram).",
             responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
def predict(req: PredictRequest):
    require_model()
    if len(req.text.split()) < C.MIN_WORDS_PREDICT:
        raise ApiError(422, "TEXT_TOO_SHORT", f"Nội dung cần tối thiểu {C.MIN_WORDS_PREDICT} từ")
    t0 = time.perf_counter()
    out = AI.predict_full(req.text, req.summary)
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return out
