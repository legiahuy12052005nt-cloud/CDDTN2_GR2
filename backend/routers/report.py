"""Router report – UC-07: xuất báo cáo PDF, CSV (FR-22, FR-23)."""
from typing import Literal

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from backend.core.deps import require_data, require_model
from backend.schemas.api import ErrorResponse
from backend.services import report_service as RS

router = APIRouter(tags=["Báo cáo"])


@router.get("/report/pdf", summary="Tạo và tải báo cáo PDF tiếng Việt (FR-22)", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}, 409: {"model": ErrorResponse}})
async def report_pdf():
    st = require_model()
    pdf = await run_in_threadpool(RS.build_pdf, st)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="bao_cao_foodreview_{st.version}.pdf"'})


@router.get("/export/{table}", summary="Tải CSV kết quả (FR-23)", response_class=Response,
            responses={200: {"content": {"text/csv": {}}}, 409: {"model": ErrorResponse}})
def export(table: Literal["predictions", "product_risk", "topics", "monthly", "model_metrics", "forecast"]):
    st = require_model() if table in ("predictions", "model_metrics") else require_data()
    data, name = RS.export_csv(st, table)
    return Response(data, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})
