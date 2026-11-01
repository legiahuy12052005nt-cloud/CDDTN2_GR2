"""Điểm khởi động backend FoodReview Insight (FastAPI).

Chạy:  uvicorn backend.main:app --reload --port 8000   (từ thư mục gốc dự án)
Tài liệu API tự sinh: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core import config as C

load_dotenv(C.BASE_DIR / ".env")   # GEMINI_API_KEY – không đưa .env lên GitHub (NFR-05)

from backend.core.errors import ApiError  # noqa: E402
from backend.core.state import STATE  # noqa: E402
from backend.routers import ai, analytics, forecast, model, predict, report, upload  # noqa: E402
from backend.schemas.api import API_CONTRACT_VERSION, HealthResponse  # noqa: E402
from backend.services import ai_service as AI  # noqa: E402
from backend.services import pipeline as PL  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    STATE.load_from_disk()          # QĐ-02: kết quả phiên trước được nạp lại khi khởi động
    yield


app = FastAPI(title="FoodReview Insight API", version=API_CONTRACT_VERSION, lifespan=lifespan,
              description="Hợp đồng API của đề tài Phân tích & dự báo mức độ hài lòng của khách hàng "
                          "từ dữ liệu đánh giá thực phẩm trên Amazon (Chuyên đề tốt nghiệp 2 – ĐH Văn Lang).")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["Content-Disposition"])


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR",
                        "message": f"Tham số không hợp lệ: {'.'.join(str(x) for x in first.get('loc', []))} – {first.get('msg', '')}",
                        "details": {"errors": [{k: str(v) for k, v in e.items() if k in ('loc', 'msg', 'type')} for e in exc.errors()]}}})


@app.get("/api/health", response_model=HealthResponse, tags=["Hệ thống"], summary="Kiểm tra hệ thống đang chạy")
def health():
    ai_st = AI.status()
    job = PL.running_job()
    ds = None
    if STATE.dataset_loaded:
        m = STATE.meta
        ds = {"file_name": m.get("file_name"), "dataset_version": STATE.version, "n_reviews": m.get("n_reviews"),
              "n_products": m.get("n_products"), "date_min": m.get("date_min"), "date_max": m.get("date_max"),
              "last_full_month": m.get("last_full_month"), "created_at": m.get("created_at")}
    return HealthResponse(dataset_loaded=STATE.dataset_loaded, model_ready=STATE.model_ready, gemini_configured=ai_st["configured"],
                          gemini_model=ai_st["model"], gemini_error=ai_st["last_error"],
                          sample_available=upload.SAMPLE_PATH.exists(), raw_available=upload.RAW_PATH.exists(),
                          job_running=job["job_id"] if job else None, dataset=ds)


for r in (upload.router, analytics.router, model.router, predict.router, forecast.router, ai.router, report.router):
    app.include_router(r, prefix="/api")
