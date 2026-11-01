"""Cấu hình dùng chung cho toàn bộ backend và notebook phân tích.

Mọi hằng số nghiệp vụ (ngưỡng cảnh báo, điều kiện dự báo, tham số tách dữ liệu)
được đặt ở một chỗ để thiết kế chi tiết (báo cáo buổi 5) và mã nguồn khớp nhau.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]          # backend/
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_SAMPLE = BASE_DIR / "data" / "sample"
MODELS_DIR = BASE_DIR / "models"
CACHE_DIR = BASE_DIR / "cache"
if os.getenv("FRI_WORK_DIR"):                            # kiểm thử: ghi kết quả vào thư mục tạm, không đụng dữ liệu thật
    _W = Path(os.environ["FRI_WORK_DIR"])
    DATA_PROCESSED, MODELS_DIR, CACHE_DIR = _W / "processed", _W / "models", _W / "cache"

RANDOM_STATE = 42                     # NFR-08: cố định để tái lập kết quả

# ---- Nạp & làm sạch (FR-01, FR-02, FR-04) ----
MAX_UPLOAD_MB = 400
REQUIRED_COLUMNS = ["Score", "Time", "Text"]
OPTIONAL_COLUMNS = ["Id", "ProductId", "UserId", "ProfileName", "Summary",
                    "HelpfulnessNumerator", "HelpfulnessDenominator"]
DEDUP_KEYS = ["UserId", "Time", "Text"]   # cùng người, cùng thời điểm, cùng nội dung
MIN_WORDS_PREDICT = 3                     # FR-14: tối thiểu 3 từ khi tự nhập

# ---- Mô hình dự đoán (FR-10, FR-11) ----
TEST_SIZE = 0.20                      # 80/20 theo FR-11
VAL_SIZE_OF_TRAIN = 0.125             # 10% tổng dữ liệu dùng làm validation
TRAIN_SAMPLE_MAX = 100_000            # file lớn: lấy mẫu phân tầng để huấn luyện (B4 – điểm nghẽn)
TFIDF_MAX_FEATURES = 200_000
TFIDF_NGRAM = (1, 2)
TFIDF_MIN_DF = 3
MISMATCH_PROB = 0.80                  # FR-13
# Kiểm tra theo thời gian (notebook 02, mục “trôi dữ liệu”): học trên đánh giá trước năm cuối, kiểm tra trên năm cuối.
# Cùng cỡ mẫu với chế độ ứng dụng (80.000 học / 20.000 kiểm tra) để so sánh trực tiếp với cách chia ngẫu nhiên.
TIME_CHECK_TRAIN_MAX = 80_000
TIME_CHECK_TEST_MAX = 20_000
TIME_CHECK_MIN_TRAIN = 300
TIME_CHECK_MIN_TEST = 100
# Kết quả thực nghiệm buổi 5 trên bộ đầy đủ (notebook 02) – chỉ hiển thị khi dữ liệu đang dùng là bộ đầy đủ
NOTEBOOK_REFERENCE = {"n_clean": 393_890, "train": 275_723, "test": 78_778, "f1_macro3": 0.7193,
                      "out_of_time_train": 100_000, "out_of_time_test": 139_179, "out_of_time_f1": 0.7081}

# ---- Chủ đề phàn nàn (FR-18) ----
TOPIC_K_RANGE = range(5, 13)

# ---- Chỉ số hài lòng, dự báo (FR-19, FR-20) ----
FORECAST_MIN_REVIEWS_PER_MONTH = 700  # chuỗi toàn bộ: SE điểm TB tháng <= 0,05 sao
FORECAST_TEST_MONTHS = 12             # NFR-04
PRODUCT_FORECAST_MIN_MONTHS = 36      # FR-20: >= 36 tháng có đánh giá

# ---- Cảnh báo sản phẩm (FR-21) – ngưỡng chốt sau EDA buổi 5 ----
RISK_WINDOW_MONTHS = 3
RISK_MIN_REVIEWS_PER_WINDOW = 10
RISK_HIGH_DELTA = -0.50               # điểm TB 3 tháng gần nhất giảm >= 0,5 sao
RISK_HIGH_NEG = 0.40                  # hoặc tỷ lệ tiêu cực 3 tháng gần nhất >= 40%
RISK_MID_DELTA = -0.25
RISK_MID_NEG = 0.25
RISK_BACKTEST_OFFSETS = (6, 3)        # kiểm tra ngược: gắn mức tại as_of − 6 và as_of − 3 tháng, xem 3 tháng tiếp theo
RISK_BACKTEST_MIN_NEXT = 5            # số đánh giá tối thiểu ở 3 tháng tiếp theo (notebook 05)

SENTIMENT_MAP = {1: "Tiêu cực", 2: "Tiêu cực", 3: "Trung tính", 4: "Tích cực", 5: "Tích cực"}

# ---- Siêu tham số đã chọn ở thực nghiệm buổi 5 (notebook 02, 03) ----
# Mô hình dùng để dự đoán: chọn trên tập validation ở thực nghiệm E-C1 (notebook 02, mục 5.2.4).
# Ứng dụng vẫn huấn luyện NB, SVM để hiển thị bảng so sánh (FR-11) nhưng KHÔNG chọn lại trên tập kiểm tra
# (tránh đánh giá lạc quan) và giữ LR vì hệ số của LR dùng để giải thích dự đoán (FR-12, FR-15).
SELECTED_MODEL = "LR"
LR_C = 4.0
NB_ALPHA = 0.3
SVM_C = 0.3
TOPIC_K = 9

# ---- Trợ lý AI (FR-25 – FR-28) ----
GEMINI_MODEL_DEFAULT = "gemini-flash-latest"
# GEMINI_MODEL trong .env được thử trước; lần lượt thử các model dưới đây nếu model đó không tồn tại với khóa đang dùng
GEMINI_FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
AI_MAX_REVIEWS = 30
AI_REVIEW_MAX_WORDS = 120
AI_RECENT_MONTHS = 12                 # ưu tiên đánh giá trong 12 tháng gần nhất khi chọn bằng chứng gửi Gemini
AI_TIMEOUT_SECONDS = 30

FULL_DATASET_ROWS = 393_890            # số dòng sạch của bộ đầy đủ (dùng để co giãn ngưỡng)


def satisfaction_index(stars):
    """Quy điểm sao (1–5) về chỉ số hài lòng 0–100 (thuật ngữ SRS bảng 2.4)."""
    return (stars - 1) / 4 * 100


def monthly_threshold(n_clean: int) -> int:
    """Ngưỡng số đánh giá/tháng để đưa tháng vào chuỗi dự báo toàn bộ.

    Bộ đầy đủ: 700 (SE điểm TB tháng ≤ 0,05 sao). File nhỏ hơn: co giãn theo tỷ lệ số dòng,
    tối thiểu 30 để chuỗi vẫn đủ dài cho mô hình.
    """
    return int(min(FORECAST_MIN_REVIEWS_PER_MONTH, max(30, round(FORECAST_MIN_REVIEWS_PER_MONTH * n_clean / FULL_DATASET_ROWS))))
