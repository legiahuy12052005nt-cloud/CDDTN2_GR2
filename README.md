# FoodReview Insight

Ứng dụng web phân tích và dự báo mức độ hài lòng của khách hàng từ dữ liệu đánh giá thực phẩm trên Amazon
(Chuyên đề tốt nghiệp 2 – Khoa CNTT, ĐH Văn Lang). Kiến trúc phân lớp: React (trình bày) – FastAPI (nghiệp vụ) –
CSV/joblib/JSON (dữ liệu); Gemini API là dịch vụ ngoài, chỉ backend gọi.

Tải file CSV (định dạng Amazon Fine Food Reviews) → backend chạy nền 7 bước: kiểm tra → làm sạch R1–R9 → EDA →
huấn luyện 3 mô hình (NB, Linear SVM, Logistic Regression) trên dữ liệu đã làm sạch, dùng Logistic Regression
(cấu hình chọn trên validation ở notebook 02) để dự đoán, kèm kiểm tra theo thời gian (học trên dữ liệu cũ, kiểm tra năm cuối) →
chủ đề phàn nàn (NMF) → dự báo chỉ số hài lòng (ETS) → gắn mức rủi ro từng sản phẩm, kèm kiểm tra ngược quy tắc.
Dashboard 9 tab đọc kết quả thật qua 20 API.

## 1. Chuẩn bị (≈ 10 phút)
1. Cài Python 3.11, Node.js 22 LTS (hoặc Docker Desktop).
2. Tải `Reviews.csv` từ Kaggle (Amazon Fine Food Reviews) vào `backend/data/raw/`
   (MD5 `c3c950ae0be8b0736477c89d052d33fd`). Mẫu 100.000 dòng có sẵn ở `backend/data/sample/`
   (tạo lại bằng `python scripts/make_sample.py`).
3. **Khóa Gemini (cho trợ lý AI):** sao chép `backend/.env.example` thành `backend/.env`, điền
   `GEMINI_API_KEY=<khóa của bạn>`, lưu file rồi khởi động lại backend. Hỗ trợ khóa Google AI Studio (`AIza…`)
   và khóa Vertex AI chế độ express (`AQ.…`) – backend tự nhận loại khóa và tự chọn model còn hoạt động.
   Chưa có khóa: trợ lý vẫn trả lời câu hỏi về dữ liệu theo quy tắc; phân tích nguyên nhân dùng chủ đề NMF.

## 2. Chạy bằng Docker (một lệnh)
```bash
docker compose up --build        # backend: http://localhost:8000/docs · frontend: http://localhost:5173
```

## 3. Chạy không dùng Docker
```bash
python3.11 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --port 8000                        # chạy từ thư mục gốc dự án
cd frontend && npm ci && npm run dev                        # cửa sổ thứ hai → http://localhost:5173
```
Mở http://localhost:5173 → chọn “Mẫu 100.000 đánh giá” (≈ 2–3 phút) hoặc “Toàn bộ Reviews.csv” (≈ 3–4 phút),
hoặc kéo thả file CSV của bạn. Kết quả lưu ở `backend/data/processed`, `backend/models`, `backend/cache` và được nạp lại
khi khởi động máy chủ, nên lần sau mở ứng dụng vào thẳng dashboard.

Cũng có thể gọi API trực tiếp: `curl -X POST "http://localhost:8000/api/data/sample?kind=full"` rồi theo dõi
`GET /api/jobs/{job_id}`.

## 4. Chức năng chính (9 tab)
| Tab | Nội dung |
|---|---|
| Tổng quan | Chỉ số hài lòng, KPI, điểm cần chú ý, xu hướng + dự báo 12 tháng, phân bố sao, sản phẩm rủi ro, chủ đề phàn nàn, nhật ký làm sạch, giới hạn của phân tích |
| Phân tích (EDA) | Bộ lọc tháng/sao/cảm xúc/sản phẩm; số đánh giá và điểm theo tháng; độ dài; từ đặc trưng (log-odds); chất lượng dữ liệu gốc |
| Mô hình ML | So sánh B0/NB/SVM/LR, ma trận nhầm lẫn 3 lớp/5 sao, từ khóa tăng/giảm số sao, đánh giá mâu thuẫn, kiểm tra theo thời gian, đối chiếu notebook 02 |
| Tự nhập dự đoán | Dự đoán số sao, cảm xúc, chỉ số hài lòng, tô màu từ ảnh hưởng, chủ đề + gợi ý hành động, lịch sử |
| Sản phẩm & cảnh báo | Bảng 67 nghìn sản phẩm: tìm, lọc, sắp xếp, phân trang; 2 loại tín hiệu (đang giảm điểm / tiêu cực kéo dài); kiểm tra ngược quy tắc; ngăn chi tiết sản phẩm có dự báo và phân tích AI |
| Chủ đề phàn nàn | 9 chủ đề NMF, từ khóa, xu hướng, đánh giá mẫu, gợi ý; phân tích nguyên nhân bằng AI |
| Dự báo | Toàn bộ (ETS) hoặc từng sản phẩm (ARIMA(0,1,1)), 3/6/12 tháng, khoảng tin cậy 95%, kiểm tra lùi |
| Trợ lý AI | Nguyên nhân – giải pháp có bằng chứng review_id; chatbot đọc dữ liệu hệ thống qua 10 công cụ + kiến thức chung |
| Báo cáo | PDF tiếng Việt, 6 bảng CSV (cảnh báo, chủ đề, dự đoán, chuỗi tháng, dự báo, chỉ số mô hình), thông tin phiên, đổi dữ liệu / xóa phiên |

## 5. Tái lập kết quả phân tích của buổi 5 (EDA, baseline)
```bash
python -m ipykernel install --user --name fri311
cd notebooks
jupytext --to ipynb 0*_*.py
jupyter nbconvert --to notebook --execute --inplace 01_eda.ipynb   # lần lượt 01 → 05
```
Thứ tự bắt buộc: 01 (tạo `reviews_clean.csv`) → 02, 03, 04, 05. Mọi bước dùng `random_state = 42`.

## 6. Kiểm thử
```bash
pytest backend/tests -q
```
16 ca kiểm thử chạy trên dữ liệu tổng hợp (`backend/tests/synth.py`) trong thư mục tạm, không ghi đè dữ liệu thật
(`pytest.ini` ở thư mục gốc đã khai báo `pythonpath = .` nên chạy thẳng lệnh trên, không cần cài gói):
đủ 20 API, định dạng lỗi, quy tắc làm sạch R1–R9 trên file có lỗi (UserId trống, Score sai, Text rỗng, bản ghi trùng),
pipeline 7 bước, mọi API trả dữ liệu đúng lược đồ, kiểm tra theo thời gian (giai đoạn học trước giai đoạn kiểm tra),
sắp xếp cảnh báo (cùng mức: giảm điểm mạnh nhất trước) và loại tín hiệu khớp lý do, kiểm tra ngược quy tắc, 6 bảng CSV, bộ lọc FR-09 (lọc đồng thời, mã sản phẩm không phân biệt hoa/thường,
bộ lọc mâu thuẫn → 422), tải file không dùng được không làm mất dữ liệu đang có, dự báo khi chuỗi có tháng trống,
dự đoán, cách chọn đánh giá bằng chứng gửi Gemini, PDF/CSV,
trợ lý AI ở chế độ quy tắc và chế độ Gemini (máy chủ Gemini giả lập `backend/tests/fake_gemini.py`: gọi công cụ, tự chuyển model khi 404,
loại nguyên nhân có bằng chứng không tồn tại, khóa sai → suy giảm có kiểm soát).

## 7. Cấu trúc thư mục
```
backend/   main.py · core/ (config, state, deps, errors) · routers/ (7 router, 20 API) · schemas/api.py (hợp đồng API 1.2.0)
           services/ data · eda · model · topic · forecast · alert · ai · report · pipeline
           data/ (raw, sample, processed) · models/ · cache/ · tests/
frontend/  React 18 + Vite 5 + Tailwind 3 + Recharts · src/api/client.js ánh xạ 20 API · src/tabs/ (9 tab)
notebooks/ 01_eda · 02_model_baseline · 03_topic_baseline · 04_forecast_baseline · 05_risk_rule (+ figures/, outputs/)
docs/      openapi.json · schema_sqlite.sql · erd.png · wireframes/ · screens/
scripts/   make_sample.py · export_openapi.py
```

## 8. Quy ước làm việc
Nhánh `main` / `develop` / `feature/PB-xx-ten-ngan`; commit bắt đầu bằng mã PB; không đưa `backend/.env`, dữ liệu gốc,
mô hình đã huấn luyện lên GitHub. Đổi lược đồ API phải tăng `API_CONTRACT_VERSION` và cập nhật `docs/openapi.json`
(`python scripts/export_openapi.py`).
Sơ đồ trong tài liệu thiết kế: `python docs/diagrams/erd_build.py` (ERD) và
`mmdc -i docs/diagrams/seq_upload.mmd -o docs/seq_upload.png -c docs/diagrams/mmd_config.json -s 2` (tương tự cho seq_predict).

## 9. Thay đổi phiên bản 1.2.0 (sau buổi demo 5)
Hợp đồng API 1.1.0 → 1.2.0, chỉ bổ sung trường tùy chọn và bảng xuất mới nên tương thích ngược; `docs/openapi.json` đã xuất lại.
- **Cảnh báo sản phẩm:** thêm trường `signal` – `decline` (điểm TB 3 tháng giảm ≥ 0,25 sao, tức “bị đánh giá thấp dần”) hoặc
  `negative` (điểm không giảm nhưng tỷ lệ tiêu cực cao kéo dài); lý do ghi rõ loại tín hiệu. Sắp theo mức rủi ro: trong cùng mức,
  sản phẩm giảm điểm mạnh nhất đứng trước (trước đây sắp theo tỷ lệ tiêu cực nên một sản phẩm đang tăng điểm đứng đầu danh sách).
- **Kiểm tra ngược quy tắc cảnh báo** (như notebook 05) chạy trong pipeline: gắn mức tại 6 và 3 tháng trước tháng cuối,
  xem tỷ lệ tiêu cực 3 tháng tiếp theo theo từng mức; hiển thị ở tab Sản phẩm, trong PDF và trường `backtest` của API #10 (`GET /api/products`).
- **Kiểm tra theo thời gian cho mô hình** (như notebook 02): LR cùng cấu hình học trên 80.000 đánh giá trước năm cuối, kiểm tra
  20.000 đánh giá của năm cuối; so với cách chia ngẫu nhiên ở tab Mô hình, trong PDF và trường `time_check` của API #11 (`GET /api/model/metrics`).
  Khi dữ liệu là bộ đầy đủ, tab Mô hình đối chiếu thêm với số liệu notebook 02 (F1-macro 0,719 trên 275.723 đánh giá học)
  để giải thích vì sao dashboard (mẫu 100.000) ra 0,714.
- **Dự báo:** biểu đồ hiện đủ chuỗi dùng để dự báo (01/2007 → 09/2012, 69 tháng) thay vì 48 tháng gần nhất.
- **Báo cáo:** thêm 2 bảng CSV `forecast` và `model_metrics` (API #20).
- **Giao diện:** bảng trong khung chatbot cuộn ngang, không bị bóp thành từng chữ; câu trả lời “sản phẩm rủi ro” của chế độ quy tắc
  dùng danh sách; nút “Hỏi trợ lý AI” thu gọn thành nút tròn (rê chuột mới hiện chữ) để không che bảng, biểu đồ; tab Tổng quan
  thêm ô “Giới hạn cần biết khi đọc kết quả”.
- **Wireframe** (`docs/wireframes/`, sinh bằng `python docs/diagrams/wireframes_build.py`): vẽ lại màn hình 2 (ô giới hạn), 4 (kiểm tra
  theo thời gian), 6 (kiểm tra ngược, nhãn loại tín hiệu), 10 (6 bảng CSV); 6 màn hình còn lại không đổi.
- **Ảnh chụp màn hình** (`docs/screens/`): chụp lại toàn bộ trên bản 1.2.0 với bộ dữ liệu đầy đủ, giữ nguyên tên file và khung hình
  của bản 1.1.0 (1440 × 900, tỷ lệ 1,5×) để tài liệu đang chèn ảnh không phải sửa: `app_upload`, `app_overview`, `app_model`,
  `app_predict`, `app_product` (ngăn chi tiết sản phẩm), `app_forecast`, `app_ai`, `swagger`. Thêm 3 ảnh: `app_products`
  (cả trang Sản phẩm & cảnh báo), `app_model_full` (cả trang Mô hình ML), `app_chatbot` (chatbot trả lời sản phẩm rủi ro cao).
- **Thời gian xử lý** tăng do có thêm kiểm tra theo thời gian: mẫu 100.000 dòng ≈ 2–3 phút, toàn bộ Reviews.csv ≈ 3–4 phút
  (đo trên máy chạy thử: 163 giây và 235 giây).
