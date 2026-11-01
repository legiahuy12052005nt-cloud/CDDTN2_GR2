"""Job runner nền: validate → clean → eda → train_model → topics → forecast → alerts (UC-01, NFR-01).

train_model gồm cả kiểm tra theo thời gian (học trên dữ liệu cũ, kiểm tra trên năm cuối); alerts gồm cả kiểm tra ngược
quy tắc cảnh báo (gắn mức tại 6 và 3 tháng trước, xem 3 tháng tiếp theo).

Mỗi lần tải file sinh một dataset_version (8 ký tự đầu SHA-1 của file tải lên). Bắt đầu job mới là
“đổi file” (FR-24): xóa kết quả phiên cũ trên đĩa và trong bộ nhớ, rồi lưu kết quả mới theo QĐ-02.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid

import joblib
import pandas as pd

from backend.core import config as C
from backend.core.state import FILES, STATE, write_json
from backend.services import alert_service as AS
from backend.services import data_service as DS
from backend.services import eda_service as EDA
from backend.services import forecast_service as FS
from backend.services import model_service as MS
from backend.services import topic_service as TS

STEPS = ["validate", "clean", "eda", "train_model", "topics", "forecast", "alerts"]
WEIGHT = {"validate": 3, "clean": 11, "eda": 7, "train_model": 58, "topics": 11, "forecast": 3, "alerts": 7}
STEP_LABEL = {"validate": "Kiểm tra cấu trúc file", "clean": "Làm sạch, chuẩn hóa (R1–R9)", "eda": "Thống kê khám phá",
              "train_model": "Huấn luyện 3 mô hình, kiểm tra theo thời gian", "topics": "Tìm chủ đề phàn nàn (NMF)",
              "forecast": "Dự báo chỉ số hài lòng", "alerts": "Gắn mức rủi ro sản phẩm, kiểm tra ngược quy tắc"}
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def running_job() -> dict | None:
    return next((j for j in JOBS.values() if j["status"] in ("queued", "running")), None)


def create_job(file_name: str, n_rows_raw: int, version: str) -> dict:
    job_id = f"job_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:4]}"
    job = {"job_id": job_id, "status": "queued", "progress": 0, "current_step": None, "current_label": None, "message": None,
           "error": None, "summary": None, "file_name": file_name, "n_rows_raw": n_rows_raw, "dataset_version": version,
           "started_at": time.time(), "steps": [{"name": s, "label": STEP_LABEL[s], "status": "pending", "seconds": None} for s in STEPS]}
    JOBS[job_id] = job
    return job


def start(job: dict, raw: pd.DataFrame) -> None:
    threading.Thread(target=_run, args=(job, raw), daemon=True, name=job["job_id"]).start()


def _run(job: dict, raw: pd.DataFrame) -> None:
    with _LOCK:
        _run_locked(job, raw)


def _run_locked(job: dict, raw: pd.DataFrame) -> None:
    job["status"] = "running"
    done_w = 0

    def step(name):
        nonlocal done_w
        s = next(x for x in job["steps"] if x["name"] == name)
        s["status"] = "running"; job["current_step"] = name; job["current_label"] = STEP_LABEL[name]
        t0 = time.time()

        def progress(pct, msg=None):
            job["progress"] = min(99, int(done_w + WEIGHT[name] * pct / 100))
            if msg:
                job["message"] = msg

        def finish():
            nonlocal done_w
            s["status"] = "done"; s["seconds"] = round(time.time() - t0, 1)
            done_w += WEIGHT[name]; job["progress"] = min(99, done_w); job["message"] = None
        return progress, finish

    try:
        # 1. validate + báo cáo chất lượng (FR-02, FR-03)
        progress, finish = step("validate")
        v = DS.validate_schema(raw)
        if not v["ok"]:
            raise PipelineError(v["errors"][0]["code"], v["errors"][0]["message"])
        quality = DS.quality_report(raw)
        finish()

        # 2. clean (R1–R9)
        progress, finish = step("clean")
        progress(10, f"Làm sạch {len(raw):,} dòng".replace(",", "."))
        clean, log = DS.clean_reviews(raw)
        del raw
        if len(clean) < 200:
            raise PipelineError("TOO_FEW_ROWS", f"Chỉ còn {len(clean)} đánh giá hợp lệ sau làm sạch (cần ≥ 200)")
        if clean.sentiment.nunique() < 3:
            raise PipelineError("TOO_FEW_CLASSES", "Dữ liệu cần có đủ đánh giá tiêu cực, trung tính và tích cực để huấn luyện")
        # FR-24: đổi file → xóa phiên cũ. Chỉ xóa khi file mới đã qua kiểm tra và làm sạch hợp lệ:
        # file sai (quá ít dòng, thiếu nhóm cảm xúc) bị từ chối mà dữ liệu đang dùng vẫn còn nguyên (NFR-07)
        STATE.clear_disk()
        job["cleared"] = True
        progress(70, "Lưu bảng đánh giá đã làm sạch")
        meta = DS.dataset_meta(clean)
        meta.update({"dataset_version": job["dataset_version"], "file_name": job["file_name"], "n_rows_raw": job["n_rows_raw"],
                     "clean_log": log, "quality": quality, "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
                     "monthly_threshold": C.monthly_threshold(len(clean))})
        C.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        clean.to_csv(FILES["reviews"], index=False)
        write_json(FILES["meta"], meta)
        finish()

        # 3. EDA
        progress, finish = step("eda")
        progress(20, "Từ khóa đặc trưng theo cảm xúc (log-odds)")
        eda = EDA.precompute(clean)
        write_json(FILES["eda"], eda)
        finish()

        # 4. Huấn luyện mô hình trên dữ liệu đã làm sạch
        progress, finish = step("train_model")
        bundle, registry, pred = MS.train(clean, progress=lambda pct, msg=None: progress(pct * 0.62, msg))
        registry["dataset_version"] = job["dataset_version"]
        # kiểm tra theo thời gian: mô hình học trên dữ liệu cũ có còn đúng với năm cuối không (notebook 02)
        try:
            registry["time_check"] = MS.time_check(clean, registry["selected_metrics"], progress=lambda pct, msg=None: progress(62 + pct * 0.38, msg))
        except Exception:  # noqa: BLE001 – phần kiểm tra bổ sung, lỗi không được làm hỏng cả phiên xử lý
            traceback.print_exc(); registry["time_check"] = None
        if len(clean) == C.NOTEBOOK_REFERENCE["n_clean"]:
            registry["reference"] = C.NOTEBOOK_REFERENCE
        C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, FILES["model"], compress=3)
        write_json(FILES["registry"], registry)
        pred.to_csv(FILES["predictions"], index=False)
        finish()

        # 5. Chủ đề phàn nàn
        progress, finish = step("topics")
        tb, topics, rt = TS.fit(clean, progress=progress, last_full=meta["last_full_month"])
        if tb is not None:
            joblib.dump(tb, FILES["topic_model"], compress=3)
            write_json(FILES["topics"], topics)
            rt.to_csv(FILES["review_topics"], index=False)
        finish()

        # 6. Dự báo
        progress, finish = step("forecast")
        fo = FS.precompute(clean, meta["last_full_month"])
        write_json(FILES["forecast"], fo)
        finish()

        # 7. Cảnh báo sản phẩm
        progress, finish = step("alerts")
        prod = AS.products_table(clean, meta["last_full_month"])
        prod.to_csv(FILES["products"], index=False)
        progress(70, "Kiểm tra ngược quy tắc cảnh báo")
        try:
            rbt = AS.backtest(clean, meta["last_full_month"])
        except Exception:  # noqa: BLE001
            traceback.print_exc(); rbt = None
        write_json(FILES["risk_backtest"], rbt)
        finish()

        with STATE.lock:
            STATE.reset_memory()
            STATE.df, STATE.meta, STATE.eda = clean, meta, eda
            STATE.model, STATE.registry, STATE.predictions = bundle, registry, pred
            STATE.topic_model, STATE.topics, STATE.review_topics = tb, (topics or None), (rt if tb is not None else None)
            STATE.forecast, STATE.products, STATE.risk_backtest = fo, prod, rbt
        sel = registry["selected_metrics"]
        job["summary"] = {"n_raw": meta["n_rows_raw"], "n_clean": meta["n_reviews"], "n_products": meta["n_products"],
                          "n_users": meta["n_users"], "date_min": meta["date_min"], "date_max": meta["date_max"],
                          "clean_log": log, "selected_model": registry["selected"], "f1_macro3": sel["f1_macro3"],
                          "n_topics": len(topics), "forecast_model": fo.get("model"),
                          "n_high_risk": int((prod.risk_level == "high").sum()),
                          "seconds": {s["name"]: s["seconds"] for s in job["steps"]},
                          "total_seconds": round(time.time() - job["started_at"], 1)}
        job["progress"] = 100; job["status"] = "done"; job["current_step"] = None; job["current_label"] = None
    except PipelineError as e:
        _fail(job, e.code, e.message)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _fail(job, "PIPELINE_FAILED", f"Lỗi khi xử lý: {type(e).__name__}: {str(e)[:300]}")


def _fail(job: dict, code: str, message: str) -> None:
    for s in job["steps"]:
        if s["status"] == "running":
            s["status"] = "failed"
        elif s["status"] == "pending":
            s["status"] = "skipped"
    # đã xóa phiên cũ: nạp lại phần kết quả mới đã ghi xong (NFR-07); chưa xóa: dữ liệu đang dùng vẫn nguyên trong bộ nhớ.
    # Nạp xong mới báo failed để giao diện hỏi /health ngay sau đó không thấy trạng thái “chưa có dữ liệu” tạm thời.
    if job.get("cleared"):
        STATE.load_from_disk()
    job["status"] = "failed"; job["error"] = {"code": code, "message": message, "details": None}


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message); self.code = code; self.message = message
