-- Lược đồ CSDL logic của FoodReview Insight (ánh xạ 1–1 với ERD, mục 2 tài liệu thiết kế buổi 5).
-- Phương án chính lưu CSV/joblib/JSON (QĐ-02); file này là phương án B (SQLite) nếu GVHD yêu cầu CSDL.
-- Ứng dụng giữ một phiên bản dữ liệu tại một thời điểm (QĐ-01): “Đổi file” (FR-24) xóa toàn bộ các bảng;
-- ON DELETE CASCADE bảo đảm các bảng gắn với dataset_version không còn bản ghi mồ côi.
PRAGMA foreign_keys = ON;

CREATE TABLE dataset (
  dataset_version TEXT PRIMARY KEY,                 -- 8 ký tự đầu SHA-1 của file tải lên
  file_name       TEXT NOT NULL,
  uploaded_at     TEXT NOT NULL,                    -- ISO 8601
  n_raw           INTEGER NOT NULL CHECK (n_raw >= 0),
  n_clean         INTEGER NOT NULL CHECK (n_clean >= 0),
  clean_log       TEXT,                             -- JSON: số dòng bị loại theo R1–R7
  last_full_month TEXT NOT NULL                     -- 'YYYY-MM'
);

CREATE TABLE product (
  product_id      TEXT PRIMARY KEY,                 -- ASIN, 10 ký tự
  n_reviews       INTEGER NOT NULL,
  avg_score       REAL NOT NULL CHECK (avg_score BETWEEN 1 AND 5),
  neg_rate        REAL NOT NULL CHECK (neg_rate BETWEEN 0 AND 1),
  first_month     TEXT, last_month TEXT,
  n_active_months INTEGER NOT NULL,
  forecastable    INTEGER NOT NULL CHECK (forecastable IN (0, 1))   -- n_active_months >= 36
);

CREATE TABLE review (
  review_id       INTEGER PRIMARY KEY,              -- = Id của file gốc
  dataset_version TEXT NOT NULL REFERENCES dataset(dataset_version) ON DELETE CASCADE,
  product_id      TEXT NOT NULL REFERENCES product(product_id),
  user_key        TEXT NOT NULL,                    -- SHA-1(UserId)[:12], không lưu UserId/ProfileName
  score           INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
  sentiment       TEXT NOT NULL CHECK (sentiment IN ('neg', 'neu', 'pos')),
  review_date     TEXT NOT NULL, year_month TEXT NOT NULL,
  helpful_num     INTEGER NOT NULL DEFAULT 0, helpful_den INTEGER NOT NULL DEFAULT 0,
  helpful_ratio   REAL,
  summary         TEXT, text TEXT NOT NULL,
  n_words         INTEGER NOT NULL CHECK (n_words >= 3),
  dup_count       INTEGER NOT NULL DEFAULT 1,
  CHECK (helpful_num <= helpful_den)
);
CREATE INDEX ix_review_product_month ON review(product_id, year_month);
CREATE INDEX ix_review_month ON review(year_month);

CREATE TABLE model_run (
  model_id        TEXT PRIMARY KEY,
  dataset_version TEXT NOT NULL REFERENCES dataset(dataset_version) ON DELETE CASCADE,
  algo            TEXT NOT NULL CHECK (algo IN ('LR', 'NB', 'SVM')),
  params TEXT, n_train INTEGER,
  f1_macro3 REAL, f1_neg REAL, mae REAL,
  is_selected     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE prediction (
  review_id       INTEGER PRIMARY KEY REFERENCES review(review_id) ON DELETE CASCADE,
  model_id        TEXT NOT NULL REFERENCES model_run(model_id),
  split           TEXT NOT NULL CHECK (split IN ('train', 'val', 'test')),
  pred_star       INTEGER NOT NULL CHECK (pred_star BETWEEN 1 AND 5),
  p1 REAL, p2 REAL, p3 REAL, p4 REAL, p5 REAL,
  pred_sentiment  TEXT NOT NULL,
  sat_index_pred  REAL CHECK (sat_index_pred BETWEEN 0 AND 100),
  is_mismatch     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE topic (
  topic_id INTEGER PRIMARY KEY, name TEXT NOT NULL, keywords TEXT NOT NULL,   -- JSON 10 từ khóa
  n_reviews INTEGER NOT NULL, share REAL NOT NULL
);

CREATE TABLE review_topic (
  review_id    INTEGER PRIMARY KEY REFERENCES review(review_id) ON DELETE CASCADE,
  topic_id     INTEGER NOT NULL REFERENCES topic(topic_id),
  topic_weight REAL NOT NULL
);

CREATE TABLE monthly_metric (
  scope_id   TEXT NOT NULL,                         -- 'ALL' hoặc product_id
  year_month TEXT NOT NULL,
  n INTEGER NOT NULL, avg_score REAL NOT NULL, neg_rate REAL NOT NULL, sat_index REAL NOT NULL,
  PRIMARY KEY (scope_id, year_month)
);

CREATE TABLE forecast (
  scope_id TEXT NOT NULL, year_month TEXT NOT NULL, model TEXT NOT NULL,
  sat_index REAL NOT NULL, lo REAL NOT NULL, hi REAL NOT NULL,
  PRIMARY KEY (scope_id, year_month)
);

CREATE TABLE product_risk (
  product_id  TEXT PRIMARY KEY REFERENCES product(product_id),
  as_of       TEXT NOT NULL,
  n_3m INTEGER, avg_3m REAL, neg_rate_3m REAL, n_prev_3m INTEGER, avg_prev_3m REAL, delta REAL,
  risk_level  TEXT NOT NULL CHECK (risk_level IN ('high', 'medium', 'low', 'insufficient')),
  reason      TEXT
);

CREATE TABLE ai_insight (
  insight_key     TEXT PRIMARY KEY,                 -- scope|scope_id|dataset_version
  scope           TEXT NOT NULL CHECK (scope IN ('product', 'topic')),
  scope_id        TEXT NOT NULL,
  dataset_version TEXT NOT NULL REFERENCES dataset(dataset_version) ON DELETE CASCADE,
  created_at      TEXT NOT NULL, model TEXT,
  causes TEXT NOT NULL, solutions TEXT NOT NULL,    -- JSON theo lược đồ InsightResponse
  dropped_causes  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE ai_evidence (
  insight_key TEXT NOT NULL REFERENCES ai_insight(insight_key) ON DELETE CASCADE,
  cause_index INTEGER NOT NULL,
  review_id   INTEGER NOT NULL REFERENCES review(review_id),
  PRIMARY KEY (insight_key, cause_index, review_id)
);
