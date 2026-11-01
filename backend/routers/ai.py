"""Router ai – UC-08, UC-09: trợ lý AI dùng Gemini API (FR-25 – FR-28, NFR-10). Chỉ backend gọi Gemini."""
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.schemas.api import ChatRequest, ChatResponse, ErrorResponse, InsightRequest, InsightResponse
from backend.services import ai_service as AI

router = APIRouter(tags=["Trợ lý AI"])


@router.post("/ai/insights", response_model=InsightResponse, summary="Nguyên nhân + giải pháp từ Gemini, có lưu đệm",
             description="Gửi tối đa 30 đánh giá tiêu cực của sản phẩm/chủ đề cho Gemini; mỗi nguyên nhân phải trích review_id có thật. "
                         "Không có khóa Gemini hoặc Gemini lỗi: trả kết quả đã lưu, nếu chưa có thì phân tích theo quy tắc (source = rule).",
             responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}})
async def insights(req: InsightRequest):
    return await run_in_threadpool(AI.insights, req.scope, req.id, req.refresh)


@router.post("/chat", response_model=ChatResponse, summary="Chatbot hỏi đáp dữ liệu hệ thống và kiến thức chung",
             description="Gemini được cấp 10 công cụ đọc dữ liệu thật (KPI, sản phẩm rủi ro, chủ đề, dự báo, dự đoán, tìm đánh giá…) "
                         "và tự quyết định gọi công cụ nào; câu hỏi ngoài hệ thống được trả lời bằng kiến thức chung của Gemini.")
async def chat(req: ChatRequest):
    return await run_in_threadpool(AI.chat, req.message, [h.model_dump() for h in req.history], req.context)
