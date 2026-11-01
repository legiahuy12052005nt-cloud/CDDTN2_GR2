"""Định dạng lỗi thống nhất: {"error": {"code", "message", "details"}} (mục 6.1 tài liệu thiết kế)."""
from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details})
