"""Router upload – UC-01: tải lên, kiểm tra, làm sạch dữ liệu, chạy pipeline nền (FR-01 – FR-06, FR-10, FR-24)."""
import hashlib
import io
from typing import Literal

import pandas as pd
from fastapi import APIRouter, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend.core import config as C
from backend.core.deps import require_data
from backend.core.errors import ApiError
from backend.core.state import STATE
from backend.schemas.api import ErrorResponse, JobStatus, QualityResponse, ResetResponse, UploadAccepted
from backend.services import data_service as DS
from backend.services import pipeline as PL

router = APIRouter(tags=["Dữ liệu"])
SAMPLE_PATH = C.DATA_SAMPLE / "reviews_sample_100k.csv"
RAW_PATH = C.DATA_RAW / "Reviews.csv"


def _read_csv(raw: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(raw), low_memory=False)
    except Exception as e:  # noqa: BLE001
        raise ApiError(400, "CSV_PARSE_ERROR", "Không đọc được file CSV", {"reason": str(e)[:200]})


def _accept(df: pd.DataFrame, file_name: str, raw: bytes) -> UploadAccepted:
    v = DS.validate_schema(df)
    if not v["ok"]:
        raise ApiError(400, v["errors"][0]["code"], v["errors"][0]["message"], {"errors": v["errors"]})
    if PL.running_job():
        raise ApiError(409, "JOB_RUNNING", "Đang xử lý một file khác, vui lòng chờ")
    version = hashlib.sha1(raw).hexdigest()[:8]
    job = PL.create_job(file_name, len(df), version)
    PL.start(job, df)
    return UploadAccepted(job_id=job["job_id"], dataset_version=version, file_name=file_name, n_rows_raw=len(df), validation=v)


@router.post("/upload", status_code=202, response_model=UploadAccepted, summary="Tải lên file CSV và bắt đầu xử lý nền",
             responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}})
async def upload(file: UploadFile = File(..., description="File .csv ≤ 400 MB")):
    if not file.filename.lower().endswith(".csv"):
        raise ApiError(415, "UNSUPPORTED_TYPE", "Chỉ nhận file .csv")
    raw = await file.read()
    if len(raw) > C.MAX_UPLOAD_MB * 1024 * 1024:
        raise ApiError(413, "FILE_TOO_LARGE", f"File vượt quá {C.MAX_UPLOAD_MB} MB")
    if not raw.strip():
        raise ApiError(400, "EMPTY_FILE", "File rỗng")
    df = await run_in_threadpool(_read_csv, raw)
    return _accept(df, file.filename, raw)


@router.get("/jobs/{job_id}", response_model=JobStatus, summary="Tiến trình xử lý nền (thanh tiến trình – NFR-01)",
            responses={404: {"model": ErrorResponse}})
def job_status(job_id: str):
    if job_id not in PL.JOBS:
        raise ApiError(404, "JOB_NOT_FOUND", "Không tìm thấy job")
    return PL.JOBS[job_id]


@router.post("/data/sample", status_code=202, response_model=UploadAccepted, summary="Dùng dữ liệu có sẵn trên máy chủ",
             description="kind = sample: mẫu phân tầng 100.000 dòng (data/sample); kind = full: toàn bộ Reviews.csv (data/raw)",
             responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
async def use_sample(kind: Literal["sample", "full"] = Query("sample")):
    path = SAMPLE_PATH if kind == "sample" else RAW_PATH
    if not path.exists():
        raise ApiError(404, "SAMPLE_NOT_FOUND", "Chưa có dữ liệu mẫu – chạy scripts/make_sample.py" if kind == "sample"
                       else "Chưa có data/raw/Reviews.csv – tải bộ Amazon Fine Food Reviews và đặt vào thư mục này")
    raw = await run_in_threadpool(path.read_bytes)
    df = await run_in_threadpool(_read_csv, raw)
    return _accept(df, path.name, raw)


@router.get("/data/quality", response_model=QualityResponse, summary="Báo cáo chất lượng dữ liệu và 20 dòng đầu (FR-03)",
            responses={409: {"model": ErrorResponse}})
def quality():
    st = require_data()
    q = st.meta.get("quality", {})
    return {"meta": st.meta_block(), "n_rows": q.get("n_rows", st.meta.get("n_rows_raw", 0)), "n_columns": q.get("n_columns", 0),
            "n_duplicates": q.get("n_duplicates", 0), "n_helpfulness_invalid": q.get("n_helpfulness_invalid", 0),
            "missing_by_column": q.get("missing_by_column", {}), "time_min": q.get("time_min"), "time_max": q.get("time_max"),
            "clean_log": st.meta.get("clean_log", {}), "preview": q.get("preview", []), "file_name": st.meta.get("file_name"),
            "n_clean": st.meta.get("n_reviews")}


@router.post("/session/reset", response_model=ResetResponse, summary="Đổi file, xóa phiên hiện tại (FR-24)",
             responses={409: {"model": ErrorResponse}})
def reset():
    if PL.running_job():
        raise ApiError(409, "JOB_RUNNING", "Đang xử lý dữ liệu, chưa thể xóa phiên")
    removed = STATE.clear_disk()
    PL.JOBS.clear()
    return ResetResponse(removed=removed)
