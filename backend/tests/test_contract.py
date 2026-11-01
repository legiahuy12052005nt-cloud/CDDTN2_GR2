"""Kiểm thử hợp đồng API và luồng chính trên dữ liệu tổng hợp (PB-03, PB-11).

- đủ 20 đường dẫn của hợp đồng; lỗi đúng định dạng {"error": {code, message, details}}
- quy tắc làm sạch R1–R9 trên file có lỗi; mô hình dự đoán là cấu hình chọn trên validation (LR)
- chọn đánh giá bằng chứng gửi Gemini đúng mục 5.6 (≤ 30, ưu tiên 12 tháng gần nhất, không gửi user_key)
- tải file → pipeline nền 7 bước → mọi API trả dữ liệu thật đúng lược đồ
- chatbot/insights: chế độ quy tắc (không có khóa) và chế độ Gemini (máy chủ Gemini giả lập: gọi công cụ, kiểm tra bằng chứng)
"""
import io
import os
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ai_service as AI
from backend.tests import fake_gemini
from backend.tests.synth import make

client = TestClient(app)
EXPECTED = {
    ("GET", "/api/health"), ("POST", "/api/upload"), ("GET", "/api/jobs/{job_id}"), ("POST", "/api/data/sample"),
    ("GET", "/api/data/quality"), ("POST", "/api/session/reset"), ("GET", "/api/kpi"), ("GET", "/api/eda/{chart}"),
    ("GET", "/api/topics"), ("GET", "/api/products"), ("GET", "/api/model/metrics"), ("GET", "/api/model/keywords"),
    ("GET", "/api/reviews/mismatch"), ("POST", "/api/predict"), ("GET", "/api/satisfaction"), ("GET", "/api/forecast"),
    ("POST", "/api/ai/insights"), ("POST", "/api/chat"), ("GET", "/api/report/pdf"), ("GET", "/api/export/{table}"),
}


def test_all_20_endpoints_declared():
    spec = client.get("/openapi.json").json()
    assert {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops} == EXPECTED


def test_errors_before_data():
    client.post("/api/session/reset")
    assert client.get("/api/health").json()["dataset_loaded"] is False
    r = client.get("/api/kpi")
    assert r.status_code == 409 and r.json()["error"]["code"] == "DATASET_NOT_LOADED"
    r = client.post("/api/predict", json={"text": "great coffee, fresh and tasty"})
    assert r.status_code == 409 and r.json()["error"]["code"] in ("MODEL_NOT_READY", "DATASET_NOT_LOADED")


def test_clean_rules_on_messy_file():
    """R1–R9 chịu được file thực tế: UserId trống, Score sai, Text rỗng, bản ghi trùng."""
    import numpy as np
    from backend.services import data_service as DS
    df = make(300)
    df.loc[df.index[:10], "UserId"] = np.nan                     # ô UserId trống không được làm sập pipeline
    df.loc[df.index[10], "Score"] = 7                            # R1
    df.loc[df.index[11], "Text"] = "   "                         # R3
    dup = df.iloc[[20]].assign(Id=10_000, ProductId="B00DUPLIC8")  # R5: cùng (UserId, Time, Text), khác mã sản phẩm
    clean, log = DS.clean_reviews(pd.concat([df, dup], ignore_index=True))
    assert log["r1_invalid_score"] == 1 and log["r3_empty_text"] == 1 and log["r5_duplicates"] >= 1
    assert len(clean) == log["n_clean"] and clean.dup_count.min() >= 1 and clean.review_id.is_unique
    assert "ProfileName" not in clean.columns and "UserId" not in clean.columns          # R8, R9


def test_upload_errors():
    r = client.post("/api/upload", files={"file": ("bad.csv", b"Score,Time\n5,1303862400\n", "text/csv")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_COLUMN"
    r = client.post("/api/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_TYPE"


@pytest.fixture(scope="module")
def loaded():
    buf = io.BytesIO(); make().to_csv(buf, index=False)
    r = client.post("/api/upload", files={"file": ("synth.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    for _ in range(300):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert j["status"] == "done", j
    assert [s["status"] for s in j["steps"]] == ["done"] * 7
    return j


def test_dashboard_endpoints(loaded):
    h = client.get("/api/health").json()
    assert h["dataset_loaded"] and h["model_ready"] and h["dataset"]["n_reviews"] == 4000
    k = client.get("/api/kpi").json()
    assert k["n_reviews"] == 4000 and 0 <= k["satisfaction_index"] <= 100 and k["model_f1_macro"] is not None
    assert client.get("/api/kpi?score=1").json()["n_reviews"] < 4000
    for c in ["score_dist", "monthly", "length_by_score", "keywords", "top_products"]:
        r = client.get(f"/api/eda/{c}?date_from=2009-01")
        assert r.status_code == 200 and r.json()["data"], c
    q = client.get("/api/data/quality").json()
    assert q["n_rows"] == 4000 and len(q["preview"]) == 20 and "ProfileName" not in q["preview"][0]


def test_eda_filters(loaded):
    """FR-09: lọc đồng thời; mã sản phẩm không phân biệt hoa/thường; bộ lọc mâu thuẫn trả 422 có thông điệp rõ."""
    pid = client.get("/api/eda/top_products").json()["data"][0]["product_id"]
    up = client.get(f"/api/kpi?product_id={pid}").json()
    assert up["n_reviews"] > 0
    assert client.get(f"/api/kpi?product_id=%20{pid.lower()}%20").json()["n_reviews"] == up["n_reviews"]
    both = client.get(f"/api/kpi?product_id={pid}&score=1&sentiment=neg&date_from=2008-01&date_to=2012-12").json()
    assert both["n_reviews"] == client.get(f"/api/kpi?product_id={pid}&score=1").json()["n_reviews"]
    for bad in ["score=2&sentiment=pos", "score=3&sentiment=neg", "date_from=2012-01&date_to=2011-01"]:
        r = client.get(f"/api/kpi?{bad}")
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR" and r.json()["error"]["message"], bad
        assert client.get(f"/api/eda/monthly?{bad}").status_code == 422, bad
    assert client.get("/api/kpi?product_id=NOPE").json()["n_reviews"] == 0          # AND: không có đánh giá khớp → 0, không lỗi
    m = client.get(f"/api/eda/monthly?product_id={pid}&sentiment=pos").json()["data"]
    assert m and all(x["neg_rate"] == 0 for x in m)
    assert client.get("/api/topics?product_id=NOPE").status_code == 404


def test_failed_upload_keeps_current_data(loaded):
    """FR-24 + NFR-07: file mới không dùng được (còn < 200 dòng sau làm sạch) bị từ chối, dữ liệu đang dùng không bị xóa."""
    buf = io.BytesIO(); make(150, seed=3).to_csv(buf, index=False)
    r = client.post("/api/upload", files={"file": ("small.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 202, r.text
    for _ in range(100):
        j = client.get(f"/api/jobs/{r.json()['job_id']}").json()
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert j["status"] == "failed" and j["error"]["code"] == "TOO_FEW_ROWS"
    h = client.get("/api/health").json()
    assert h["dataset_loaded"] and h["model_ready"] and h["dataset"]["n_reviews"] == 4000
    assert client.get("/api/kpi").json()["n_reviews"] == 4000


def test_forecast_month_gap():
    """Chuỗi toàn bộ có tháng không có đánh giá nào: không được sinh NaN (API #16 trả JSON hợp lệ)."""
    import math
    from backend.services import data_service as DS
    from backend.services import forecast_service as FS
    clean, _ = DS.clean_reviews(make(6000, months=60, seed=1))
    clean = clean[clean.year_month != "2010-06"]
    out = FS.precompute(clean, sorted(clean.year_month.unique())[-2])
    assert out["forecast"] and all(math.isfinite(p[k]) for p in out["forecast"] for k in ("sat_index", "lo", "hi"))
    assert out["series_start"] > "2010-06"


def test_model_endpoints(loaded):
    m = client.get("/api/model/metrics").json()
    assert {x["model"] for x in m["models"]} == {"B0", "NB", "SVM", "LR"} and sum(x["selected"] for x in m["models"]) == 1
    assert m["selected"] == "LR"          # cấu hình chọn trên validation (E-C1); tập kiểm tra không dùng để chọn lại
    assert len(m["confusion3"]) == 3 and len(m["confusion5"]) == 5
    kw = client.get("/api/model/keywords?n=10").json()
    assert len(kw["up"]) == 10 and kw["up"][0]["weight"] > 0 > kw["down"][0]["weight"]
    assert client.get("/api/reviews/mismatch?threshold=0.5").status_code == 200
    # kiểm tra theo thời gian: học trên dữ liệu trước năm cuối, kiểm tra trên năm cuối – không trùng giai đoạn
    tc = m["time_check"]
    assert tc and tc["n_train"] > 0 and tc["n_test"] > 0 and tc["train_to"] < tc["test_from"]
    assert 0 <= tc["f1_macro3"] <= 1 and abs(tc["gap"] - (tc["random_f1_macro3"] - tc["f1_macro3"])) < 1e-3
    assert m["reference"] is None                                   # dữ liệu tổng hợp ≠ bộ đầy đủ → không hiện số notebook


def test_predict(loaded):
    r = client.post("/api/predict", json={"text": "The coffee was stale and tastes awful, box was crushed", "summary": "Stale"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["sentiment"] == "neg" and p["pred_star"] <= 2 and abs(sum(p["proba"].values()) - 1) < 1e-3
    assert any(t["weight"] < 0 for t in p["tokens"]) and p["model_info"]["n_train"] > 0
    p = client.post("/api/predict", json={"text": "delicious, love it, highly recommend this honey"}).json()
    assert p["sentiment"] == "pos" and p["topic"] is None
    p = client.post("/api/predict", json={"text": "cà phê này rất dở và cũ"}).json()
    assert p["note"]
    p = client.post("/api/predict", json={"text": "great-tasting,fresh,crunchy,salty,sweet,tasty,delicious crackers yes"}).json()
    assert 0 <= p["known_token_ratio"] <= 1                       # tỷ lệ từ đã biết không vượt 100%
    assert client.post("/api/predict", json={"text": "too short"}).json()["error"]["code"] == "TEXT_TOO_SHORT"


def test_products_topics_forecast(loaded):
    r = client.get("/api/products?sort=risk&order=desc&page_size=5").json()
    assert r["page"]["total"] == 30 and r["items"][0]["risk_level"] == "high" and r["counts"]["high"] >= 1
    pid = r["items"][0]["product_id"]
    assert client.get(f"/api/products?q={pid[-4:]}").json()["page"]["total"] >= 1
    # cùng mức rủi ro: giảm điểm mạnh nhất đứng trước; mỗi sản phẩm có cảnh báo đều có loại tín hiệu khớp lý do
    full = client.get("/api/products?sort=risk&order=desc&page_size=100").json()["items"]
    for lvl in ("high", "medium"):
        ds = [x["delta"] for x in full if x["risk_level"] == lvl and x["delta"] is not None]
        assert ds == sorted(ds), lvl
    for x in full:
        if x["risk_level"] in ("high", "medium"):
            assert x["signal"] in ("decline", "negative") and x["reason"]
            assert (x["signal"] == "decline") == (x["delta"] <= -0.25)
            assert x["signal"] == "decline" or "kéo dài" in x["reason"]
    bt = r["backtest"]
    assert bt and bt["points"] and all(p["next_from"] > p["as_of"] for p in bt["points"])
    assert set(bt["summary"]) == {"high", "medium", "low"}
    t = client.get("/api/topics").json()
    assert t["topics"] and len(t["topics"][0]["keywords"]) == 10
    last_full = client.get("/api/kpi").json()["last_full_month"]
    assert all(p["month"] <= last_full for x in t["topics"] for p in x["trend"])   # xu hướng chỉ dùng tháng trọn vẹn
    assert client.get(f"/api/topics?product_id={pid}").status_code == 200
    f = client.get("/api/forecast?months=6").json()
    assert f["eligible"] and len(f["forecast"]) == 6 and f["backtest"]
    fp = client.get(f"/api/forecast?product_id={pid}&months=3").json()
    assert fp["scope"] == "product" and (fp["eligible"] is False or len(fp["forecast"]) == 3)
    assert client.get("/api/forecast?months=5").status_code == 422
    assert client.get("/api/forecast?product_id=NOPE").status_code == 404
    s = client.get(f"/api/satisfaction?product_id={pid}").json()
    assert s["series"] and s["scope"] == "product"


def test_ai_evidence_selection(loaded):
    """Mục 5.6: ≤ 30 đánh giá, ưu tiên 12 tháng gần nhất, mỗi đánh giá ≤ 120 từ, không gửi user_key; khóa lưu đệm không phân biệt hoa/thường."""
    from backend.core.state import STATE
    pid = client.get("/api/products?sort=risk").json()["items"][0]["product_id"]
    ctx = AI._insight_context("product", pid.lower())
    assert 0 < len(ctx["reviews"]) <= 30 and all(len(r["text"].split()) <= 121 for r in ctx["reviews"])
    assert all("user_key" not in r for r in ctx["reviews"])
    recent = STATE.df[(STATE.df.product_id == pid) & (STATE.df.score <= 2) & (STATE.df.year_month >= AI._recent_cutoff())]
    sent_months = [r["date"][:7] for r in ctx["reviews"]]
    assert sum(m >= AI._recent_cutoff() for m in sent_months) == min(len(recent), 30)
    t = AI._insight_context("topic", "0")
    assert 0 < len(t["reviews"]) <= 30


def test_report_and_exports(loaded):
    r = client.get("/api/report/pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) > 20_000
    for t in ["product_risk", "topics", "predictions", "monthly", "model_metrics", "forecast"]:
        r = client.get(f"/api/export/{t}")
        assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf"), t
    mm = pd.read_csv(io.BytesIO(client.get("/api/export/model_metrics").content), encoding="utf-8-sig")
    assert set(mm.model) == {"B0", "NB", "SVM", "LR"} and mm.split.str.contains("theo thời gian").any()
    assert client.get("/api/export/nope").status_code == 422


def test_ai_rule_mode(loaded):
    os.environ.pop("GEMINI_API_KEY", None)
    c = client.post("/api/chat", json={"message": "Những sản phẩm nào đang rủi ro cao?"}).json()
    assert c["source"] == "rule" and "rủi ro cao" in c["answer"] and c["data_used"]
    assert "|---|" not in c["answer"]                               # danh sách, không phải bảng nhiều cột trong khung chat hẹp
    c = client.post("/api/chat", json={"message": 'Có bao nhiêu đánh giá nhắc tới "stale"?'}).json()
    assert "Tìm kiếm đánh giá" in c["data_used"] and "stale" in c["answer"]
    c = client.post("/api/chat", json={"message": "Dự đoán: tốt"}).json()
    assert "tối thiểu 3 từ" in c["answer"]                       # cùng điều kiện FR-14 với API #14
    pid = client.get("/api/products?sort=risk").json()["items"][0]["product_id"]
    i = client.post("/api/ai/insights", json={"scope": "product", "id": pid}).json()
    assert i["source"] == "rule" and i["causes"] and all(c["evidence"] for c in i["causes"])
    assert client.post("/api/ai/insights", json={"scope": "product", "id": "NOPE"}).status_code == 404
    for tid in ("-1", "99", "x"):
        assert client.post("/api/ai/insights", json={"scope": "topic", "id": tid}).status_code == 404, tid


def test_ai_gemini_mode(loaded):
    base = fake_gemini.start()
    os.environ.update(GEMINI_API_KEY="AQ.fake-test-key", GEMINI_BASE_URL=base, GEMINI_MODEL="missing-model")
    AI._ACTIVE.update(mode=None, model=None)
    try:
        c = client.post("/api/chat", json={"message": "Tổng quan dữ liệu thế nào?", "context": {"page": "Tổng quan"}}).json()
        assert c["source"] == "gemini" and "get_overview" in c["answer"] and c["data_used"] == ["KPI tổng quan"], c
        assert c["model"] != "missing-model"                       # model 404 → tự chuyển model dự phòng
        c = client.post("/api/chat", json={"message": "Những sản phẩm nào rủi ro?"}).json()
        assert "list_risk_products" in c["answer"]
        c = client.post("/api/chat", json={"message": "Thời tiết Hà Nội hôm nay thế nào?"}).json()
        assert c["source"] == "gemini" and "kiến thức chung" in c["answer"] and c["data_used"] == []
        pid = client.get("/api/products?sort=risk").json()["items"][0]["product_id"]
        i = client.post("/api/ai/insights", json={"scope": "product", "id": pid, "refresh": True}).json()
        assert i["source"] == "gemini" and len(i["causes"]) == 1 and i["dropped_causes"] == 1 and len(i["solutions"]) == 1
        assert client.post("/api/ai/insights", json={"scope": "product", "id": pid}).json()["cached"] is True
        i = client.post("/api/ai/insights", json={"scope": "topic", "id": "0", "refresh": True}).json()
        assert i["causes"][0]["evidence_ids"]
        assert client.get("/api/health").json()["gemini_model"]
        os.environ["GEMINI_API_KEY"] = "BAD"; AI._ACTIVE.update(mode=None, model=None)
        c = client.post("/api/chat", json={"message": "Tổng quan?"}).json()
        assert c["source"] == "rule" and "không hợp lệ" in c["answer"]
    finally:
        for k in ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODEL"):
            os.environ.pop(k, None)
        AI._ACTIVE.update(mode=None, model=None, last_error=None)


def test_reset_last(loaded):
    r = client.post("/api/session/reset").json()
    assert r["status"] == "reset" and r["removed"]
    assert client.get("/api/kpi").status_code == 409
