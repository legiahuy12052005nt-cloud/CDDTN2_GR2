"""Điều kiện trước của API: đã có dữ liệu (409 DATASET_NOT_LOADED), mô hình đã sẵn sàng (409 MODEL_NOT_READY)."""
from backend.core.errors import ApiError
from backend.core.state import STATE


def require_data():
    if not STATE.dataset_loaded:
        raise ApiError(409, "DATASET_NOT_LOADED", "Chưa có dữ liệu – hãy tải file CSV hoặc dùng dữ liệu mẫu")
    return STATE


def require_model():
    require_data()
    if not STATE.model_ready:
        raise ApiError(409, "MODEL_NOT_READY", "Mô hình chưa huấn luyện xong")
    return STATE
