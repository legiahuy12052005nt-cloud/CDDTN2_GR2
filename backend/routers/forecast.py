"""Router forecast – UC-06: chỉ số hài lòng theo tháng và dự báo (FR-19, FR-20)."""
from typing import Optional

from fastapi import APIRouter, Query

from backend.core.deps import require_data
from backend.core.errors import ApiError
from backend.schemas.api import ErrorResponse, ForecastResponse, SatisfactionResponse
from backend.services import forecast_service as FS

router = APIRouter(tags=["Dự báo"])


def _check_product(st, product_id):
    if product_id:
        pid = product_id.strip().upper()
        if st.products is None or not (st.products.product_id == pid).any():
            raise ApiError(404, "PRODUCT_NOT_FOUND", f"Không tìm thấy sản phẩm {pid}")
        return pid
    return None


@router.get("/satisfaction", response_model=SatisfactionResponse, summary="Chỉ số hài lòng theo tháng (FR-19)",
            responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
def satisfaction(product_id: Optional[str] = None,
                 date_from: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), date_to: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$")):
    st = require_data()
    return FS.satisfaction(st, _check_product(st, product_id), date_from, date_to)


@router.get("/forecast", response_model=ForecastResponse, summary="Dự báo chỉ số hài lòng 3/6/12 tháng (FR-20)",
            responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
def forecast(product_id: Optional[str] = None, months: int = Query(12, description="Số tháng dự báo: 3, 6 hoặc 12")):
    if months not in (3, 6, 12):
        raise ApiError(422, "VALIDATION_ERROR", "months chỉ nhận 3, 6 hoặc 12")
    st = require_data()
    return FS.forecast(st, _check_product(st, product_id), months)
