"""Hợp đồng API (API contract) – lược đồ dữ liệu vào/ra của 20 API.

Đây là nguồn sự thật duy nhất cho giao tiếp frontend ↔ backend: FastAPI sinh tài liệu /docs và
file docs/openapi.json từ các lớp dưới đây. Mọi thay đổi lược đồ phải cập nhật phiên bản
API_CONTRACT_VERSION và ghi vào nhật ký thay đổi của tài liệu thiết kế.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel as _PydanticBase, ConfigDict, Field

API_CONTRACT_VERSION = "1.2.0"   # 1.1.0: chỉ bổ sung trường tùy chọn, tương thích ngược với 1.0.0
# 1.2.0: bổ sung trường tùy chọn time_check, reference (#11), signal, backtest (#10); thêm bảng xuất model_metrics, forecast (#20)


class BaseModel(_PydanticBase):
    """Lớp gốc: cho phép tên trường bắt đầu bằng model_ (model_ready, model_f1_macro)."""
    model_config = ConfigDict(protected_namespaces=())

Sentiment = Literal["neg", "neu", "pos"]
RiskLevel = Literal["high", "medium", "low", "insufficient"]


# ------------------------------- dùng chung -------------------------------- #
class ErrorBody(BaseModel):
    code: str = Field(..., examples=["MISSING_COLUMN"])
    message: str = Field(..., examples=["Thiếu cột bắt buộc: Text"])
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Meta(BaseModel):
    dataset_version: str = Field(..., description="Mã phiên bản dữ liệu (8 ký tự đầu SHA-1 của file dữ liệu tải lên)", examples=["9f2c41ab"])
    filters: dict = Field(default_factory=dict)


class Filters(BaseModel):
    date_from: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$", examples=["2011-01"])
    date_to: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$", examples=["2012-09"])
    product_id: Optional[str] = Field(None, examples=["B007JFMH8M"])
    sentiment: Optional[Sentiment] = None
    score: Optional[int] = Field(None, ge=1, le=5)


# ------------------------------ hệ thống, phiên ----------------------------- #
class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = API_CONTRACT_VERSION
    dataset_loaded: bool
    model_ready: bool
    gemini_configured: bool
    gemini_model: Optional[str] = Field(None, description="Model Gemini đang dùng sau lần gọi thành công gần nhất")
    gemini_error: Optional[str] = Field(None, description="Lỗi Gemini gần nhất (khóa sai, hết hạn mức, mất mạng)")
    sample_available: bool = False
    raw_available: bool = Field(False, description="Có file Reviews.csv đầy đủ trong data/raw")
    job_running: Optional[str] = None
    dataset: Optional[dict] = Field(None, description="Tóm tắt dữ liệu đang nạp: file, số đánh giá, khoảng thời gian")


class ValidationResult(BaseModel):
    ok: bool
    errors: list[dict] = []
    warnings: list[dict] = []


class UploadAccepted(BaseModel):
    job_id: str = Field(..., examples=["job_20261031_0001"])
    dataset_version: str
    file_name: str = Field(..., examples=["Reviews.csv"])
    n_rows_raw: int = Field(..., examples=[568454])
    validation: ValidationResult


class JobStep(BaseModel):
    name: Literal["validate", "clean", "eda", "train_model", "topics", "forecast", "alerts"]
    label: Optional[str] = None
    status: Literal["pending", "running", "done", "failed", "skipped"]
    seconds: Optional[float] = None


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    progress: int = Field(..., ge=0, le=100)
    current_step: Optional[str] = None
    current_label: Optional[str] = None
    message: Optional[str] = Field(None, description="Mô tả việc đang làm trong bước hiện tại")
    file_name: Optional[str] = None
    steps: list[JobStep]
    error: Optional[ErrorBody] = None
    summary: Optional[dict] = Field(None, description="Khi xong: n_clean, n_products, thời gian từng bước")


class QualityResponse(BaseModel):
    meta: Meta
    n_rows: int
    n_columns: int
    n_duplicates: int
    n_helpfulness_invalid: int
    missing_by_column: dict[str, int]
    time_min: Optional[str]
    time_max: Optional[str]
    file_name: Optional[str] = None
    n_clean: Optional[int] = None
    clean_log: dict[str, int] = Field(..., description="Số dòng bị loại theo từng quy tắc R1–R7")
    preview: list[dict] = Field(..., description="20 dòng đầu (đã bỏ ProfileName)")


class ResetResponse(BaseModel):
    status: Literal["reset"] = "reset"
    removed: list[str] = Field(..., examples=[["data/processed/*", "models/*.joblib", "cache/ai_insights.json"]])


# --------------------------------- tổng quan -------------------------------- #
class KpiResponse(BaseModel):
    meta: Meta
    n_reviews: int
    n_products: int
    n_users: int
    avg_score: float
    neg_rate: float = Field(..., description="Tỷ lệ đánh giá 1–2 sao, 0–1")
    model_f1_macro: Optional[float] = Field(None, description="F1-macro 3 lớp của mô hình được chọn")
    n_high_risk_products: Optional[int] = None
    satisfaction_index: float = Field(..., description="(avg_score − 1) / 4 × 100")
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    last_full_month: Optional[str] = None


ChartName = Literal["score_dist", "monthly", "length_by_score", "keywords", "top_products"]


class ChartResponse(BaseModel):
    meta: Meta
    chart: ChartName
    data: list[dict] = Field(..., description="Mảng điểm dữ liệu; cấu trúc từng phần tử theo bảng 6.x của tài liệu thiết kế")


# --------------------------------- mô hình ---------------------------------- #
class ModelMetric(BaseModel):
    model: Literal["LR", "NB", "SVM", "B0"]
    params: str
    f1_macro3: float
    f1_neg: float
    f1_neu: float
    f1_pos: float
    acc5: float
    mae: float
    fit_seconds: Optional[float] = None
    selected: bool = False
    prec_neg: Optional[float] = None
    rec_neg: Optional[float] = None
    acc3: Optional[float] = None


class ModelMetricsResponse(BaseModel):
    meta: Meta
    split: dict = Field(..., examples=[{"n_dataset": 393890, "n_used": 100000, "train": 80000, "test": 20000, "stratify": "score", "random_state": 42, "sampled": True}])
    models: list[ModelMetric]
    confusion3: list[list[int]]
    confusion5: list[list[int]]
    selected: Optional[str] = None
    trained_at: Optional[str] = None
    vectorizer: Optional[dict] = None
    n_mismatch: Optional[int] = None
    time_check: Optional[dict] = Field(None, description="Kiểm tra theo thời gian: LR học trên dữ liệu trước năm cuối, kiểm tra trên năm cuối",
                                       examples=[{"rule": "học trên đánh giá trước 2012-01-01, kiểm tra trên đánh giá từ 2012-01-01",
                                                  "n_train": 80000, "n_test": 20000, "f1_macro3": 0.705, "random_f1_macro3": 0.714, "gap": 0.009}])
    reference: Optional[dict] = Field(None, description="Kết quả notebook 02 trên bộ đầy đủ (chỉ có khi dữ liệu là bộ đầy đủ 393.890 đánh giá)")


class KeywordItem(BaseModel):
    term: str
    weight: float


class KeywordsResponse(BaseModel):
    meta: Meta
    up: list[KeywordItem]
    down: list[KeywordItem]


class MismatchItem(BaseModel):
    review_id: int
    product_id: str
    score: int
    pred_sentiment: Sentiment
    p_neg: float
    p_pos: float
    summary: str
    text: str
    pred_star: Optional[int] = None
    review_date: Optional[str] = None


class Page(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int


class MismatchResponse(BaseModel):
    meta: Meta
    page: Page
    items: list[MismatchItem]


# --------------------------------- dự đoán ---------------------------------- #
class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, examples=["The coffee arrived stale and the box was crushed. Very disappointed."])
    summary: Optional[str] = Field(None, max_length=300, examples=["Stale coffee"])
    product_id: Optional[str] = Field(None, examples=["B007JFMH8M"])


class TokenWeight(BaseModel):
    token: str
    weight: float = Field(..., description="> 0 kéo số sao lên, < 0 kéo xuống")


class TopicRef(BaseModel):
    topic_id: int
    name: str
    weight: float


class PredictResponse(BaseModel):
    pred_star: int = Field(..., ge=1, le=5)
    proba: dict[str, float] = Field(..., description="Xác suất từng mức sao, khóa '1'…'5'")
    sentiment: Sentiment
    sentiment_proba: dict[str, float]
    satisfaction_index: float = Field(..., ge=0, le=100, description="(Σ k·P(k) − 1) / 4 × 100")
    tokens: list[TokenWeight]
    topic: Optional[TopicRef] = Field(None, description="Chỉ có khi cảm xúc là Tiêu cực (FR-15)")
    suggestion: Optional[str] = Field(None, description="Gợi ý hành động theo chủ đề (FR-16)")
    latency_ms: float
    known_token_ratio: Optional[float] = Field(None, description="Tỷ lệ từ của văn bản có trong từ điển mô hình")
    note: Optional[str] = Field(None, description="Cảnh báo khi văn bản ít từ mô hình đã biết (ví dụ không phải tiếng Anh)")
    model_info: Optional[dict] = Field(None, description="Mô hình đã dùng, F1-macro, số đánh giá huấn luyện, dataset_version")


# --------------------------- chủ đề, dự báo, sản phẩm ----------------------- #
class Topic(BaseModel):
    topic_id: int
    name: str
    key: Optional[str] = None
    keywords: list[str] = Field(..., max_length=10)
    n_reviews: int
    share: float
    suggestion: Optional[str] = None
    samples: list[dict] = Field(..., description="3 đánh giá mẫu: review_id, score, summary, text")
    trend: list[dict] = Field(..., description="[{month, share}] tỷ trọng chủ đề theo tháng")


class TopicsResponse(BaseModel):
    meta: Meta
    model: str = Field(..., examples=["NMF k=9"])
    topics: list[Topic]
    product_id: Optional[str] = None
    n_negative: Optional[int] = None


class MonthPoint(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    n: int
    avg_score: float
    neg_rate: float
    sat_index: float


class SatisfactionResponse(BaseModel):
    meta: Meta
    scope: Literal["all", "product"]
    product_id: Optional[str] = None
    series: list[MonthPoint]


class ForecastPoint(BaseModel):
    month: str
    sat_index: float
    lo: float
    hi: float


class ForecastResponse(BaseModel):
    meta: Meta
    scope: Literal["all", "product"]
    product_id: Optional[str] = None
    eligible: bool
    message: Optional[str] = Field(None, examples=["Không đủ dữ liệu để dự báo (cần ≥ 36 tháng có đánh giá)"])
    model: Optional[str] = Field(None, examples=["ETS(A,Ad,N)"])
    history: list[MonthPoint] = []
    forecast: list[ForecastPoint] = []
    backtest: Optional[dict] = Field(None, examples=[{"mae_model": 0.61, "mae_naive": 1.50, "unit": "điểm chỉ số"}])
    series: Optional[dict] = Field(None, description="Chuỗi dùng để dự báo: tháng đầu/cuối, số tháng, ngưỡng đánh giá/tháng")


class ProductRow(BaseModel):
    product_id: str
    n_reviews: int
    avg_score: float
    neg_rate: float
    n_3m: int
    avg_3m: Optional[float]
    delta: Optional[float]
    risk_level: RiskLevel
    reason: str = ""
    signal: Optional[Literal["decline", "negative", ""]] = Field(None, description="decline: điểm TB đang giảm; negative: tiêu cực cao kéo dài, điểm không giảm")
    forecastable: bool
    n_prev_3m: Optional[int] = None
    avg_prev_3m: Optional[float] = None
    neg_rate_3m: Optional[float] = None
    n_active_months: Optional[int] = None
    first_month: Optional[str] = None
    last_month: Optional[str] = None


class ProductsResponse(BaseModel):
    meta: Meta
    page: Page
    items: list[ProductRow]
    counts: Optional[dict[str, int]] = Field(None, description="Số sản phẩm theo mức rủi ro")
    as_of: Optional[str] = None
    backtest: Optional[dict] = Field(None, description="Kiểm tra ngược quy tắc: gắn mức tại 6 và 3 tháng trước, tỷ lệ tiêu cực 3 tháng tiếp theo theo từng mức")


# ---------------------------------- AI -------------------------------------- #
class InsightRequest(BaseModel):
    scope: Literal["product", "topic"]
    id: str = Field(..., examples=["B00507A02Q"])
    refresh: bool = Field(False, description="True: bỏ qua cache, gọi lại Gemini")


class Evidence(BaseModel):
    review_id: int
    score: int
    summary: str
    text: Optional[str] = None
    date: Optional[str] = None
    product_id: Optional[str] = None


class Cause(BaseModel):
    title: str
    description: str
    severity: Literal["cao", "trung bình", "thấp"]
    evidence_ids: list[int] = Field(..., min_length=1)
    evidence: list[Evidence]


class Solution(BaseModel):
    cause_index: int
    action: str
    priority: Literal["cao", "trung bình", "thấp"]
    kpi: str


class InsightResponse(BaseModel):
    scope: str
    id: str
    cached: bool
    created_at: str
    model: str = Field(..., examples=["gemini-flash"])
    causes: list[Cause]
    solutions: list[Solution]
    dropped_causes: int = Field(0, description="Số nguyên nhân bị loại vì ID bằng chứng không tồn tại (NFR-10)")
    source: Literal["gemini", "rule"] = Field("gemini", description="gemini: do Gemini sinh; rule: suy giảm có kiểm soát khi không có Gemini")
    title: Optional[str] = None
    stats: Optional[str] = Field(None, description="Số liệu tóm tắt đã gửi kèm prompt")
    n_reviews_sent: Optional[int] = None
    note: Optional[str] = None
    latency_ms: Optional[float] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    context: Optional[dict] = Field(None, description="Ngữ cảnh màn hình: page, product_id, topic_id", examples=[{"page": "Sản phẩm & cảnh báo", "product_id": "B007JFMH8M"}])


class ChatResponse(BaseModel):
    answer: str
    data_used: list[str] = Field(..., description="Các công cụ dữ liệu của hệ thống mà trợ lý đã gọi để trả lời")
    cached: bool = False
    source: Literal["gemini", "rule"] = "gemini"
    model: Optional[str] = None
    latency_ms: Optional[float] = None
