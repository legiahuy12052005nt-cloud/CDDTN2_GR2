"""AlertService – quy tắc gắn mức rủi ro sản phẩm (FR-21).

Ngưỡng được chốt sau EDA buổi 5 (notebook 05_risk_rule): so sánh cửa sổ 3 tháng gần nhất (W1)
với 3 tháng liền trước (W0), tính đến tháng trọn vẹn cuối cùng của dữ liệu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.core import config as C


def compute_risk(clean: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """clean: bảng reviews_clean; as_of: 'YYYY-MM' (tháng trọn vẹn cuối cùng).

    Trả về 1 dòng/sản phẩm: n_3m, avg_3m, neg_rate_3m, n_prev_3m, avg_prev_3m, delta, risk_level, reason, signal.
    risk_level ∈ {"high", "medium", "low", "insufficient"}; signal ∈ {"decline", "negative", ""}.
    """
    end = pd.Period(as_of, "M"); w = C.RISK_WINDOW_MONTHS
    ym = pd.PeriodIndex(clean["year_month"], freq="M")
    w1 = (ym > end - w) & (ym <= end)
    w0 = (ym > end - 2 * w) & (ym <= end - w)
    a = clean[w1].groupby("product_id").agg(n_3m=("score", "size"), avg_3m=("score", "mean"),
                                            neg_rate_3m=("sentiment", lambda s: (s == "neg").mean()))
    b = clean[w0].groupby("product_id").agg(n_prev_3m=("score", "size"), avg_prev_3m=("score", "mean"))
    r = a.join(b, how="outer")
    r[["n_3m", "n_prev_3m"]] = r[["n_3m", "n_prev_3m"]].fillna(0).astype(int)
    r["delta"] = r.avg_3m - r.avg_prev_3m
    ok = (r.n_3m >= C.RISK_MIN_REVIEWS_PER_WINDOW) & (r.n_prev_3m >= C.RISK_MIN_REVIEWS_PER_WINDOW)
    high = ok & ((r.delta <= C.RISK_HIGH_DELTA) | (r.neg_rate_3m >= C.RISK_HIGH_NEG))
    mid = ok & ~high & ((r.delta <= C.RISK_MID_DELTA) | (r.neg_rate_3m >= C.RISK_MID_NEG))
    r["risk_level"] = np.select([high, mid, ok], ["high", "medium", "low"], default="insufficient")
    # Loại tín hiệu: “decline” – điểm TB đang giảm (đúng bài toán “bị đánh giá thấp dần”);
    # “negative” – điểm TB không giảm đáng kể nhưng tỷ lệ tiêu cực cao kéo dài (sản phẩm kém ổn định, không phải mới xấu đi)
    reasons, signals = [], []
    for d, n, lvl in zip(r.delta, r.neg_rate_3m, r.risk_level):
        if lvl in ("low", "insufficient"):
            reasons.append(""); signals.append(""); continue
        if pd.notna(d) and d <= C.RISK_MID_DELTA:
            parts = [f"điểm TB 3 tháng giảm {abs(d):.2f} sao".replace(".", ",")]
            if pd.notna(n) and n >= C.RISK_MID_NEG:
                parts.append(f"tỷ lệ tiêu cực {n:.0%}")
            reasons.append("; ".join(parts)); signals.append("decline")
        else:
            trend = (f"điểm TB tăng {d:+.2f} sao" if d > 0.05 else f"điểm TB gần như không đổi ({d:+.2f} sao)").replace(".", ",")
            reasons.append(f"tỷ lệ tiêu cực cao kéo dài {n:.0%} – {trend}"); signals.append("negative")
    r["reason"] = reasons
    r["signal"] = signals
    r["as_of"] = as_of
    return r.reset_index()


RISK_RANK = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}
LEVELS = ["high", "medium", "low"]


def backtest(clean: pd.DataFrame, as_of: str) -> dict | None:
    """Kiểm tra ngược quy tắc (notebook 05, mục 2): gắn mức rủi ro tại as_of − 6 và as_of − 3 tháng,
    rồi xem tỷ lệ tiêu cực, điểm TB của 3 tháng TIẾP THEO (dữ liệu quy tắc chưa nhìn thấy).

    Quy tắc có giá trị cảnh báo nếu nhóm “Cao” vẫn có tỷ lệ tiêu cực ở 3 tháng sau cao hơn hẳn nhóm “Ổn định”.
    """
    d = clean[["product_id", "score", "sentiment", "year_month"]]
    end = pd.Period(as_of, "M"); w = C.RISK_WINDOW_MONTHS
    points, rows = [], []
    for off in C.RISK_BACKTEST_OFFSETS:
        t = end - off
        nxt = (str(t + 1), str(t + w))
        rr = compute_risk(d, str(t))
        rr = rr[rr.risk_level != "insufficient"].set_index("product_id")
        if rr.empty:
            continue
        f = d[d.year_month.between(*nxt)].groupby("product_id").agg(
            n_next=("score", "size"), avg_next=("score", "mean"), neg_next=("sentiment", lambda s: (s == "neg").mean()))
        j = rr.join(f, how="inner")
        j = j[j.n_next >= C.RISK_BACKTEST_MIN_NEXT]
        if j.empty:
            continue
        j = j.assign(as_of=str(t))
        rows.append(j)
        for lvl in LEVELS:
            g = j[j.risk_level == lvl]
            if len(g):
                points.append({"as_of": str(t), "next_from": nxt[0], "next_to": nxt[1], "risk_level": lvl, "n_products": int(len(g)),
                               "neg_now": round(float(g.neg_rate_3m.mean()), 4), "neg_next": round(float(g.neg_next.mean()), 4),
                               "avg_now": round(float(g.avg_3m.mean()), 4), "avg_next": round(float(g.avg_next.mean()), 4)})
    if not rows:
        return None
    a = pd.concat(rows)
    summary = {lvl: {"n_products": int((a.risk_level == lvl).sum()),
                     "neg_next": round(float(a.loc[a.risk_level == lvl, "neg_next"].mean()), 4) if (a.risk_level == lvl).any() else None,
                     "avg_next": round(float(a.loc[a.risk_level == lvl, "avg_next"].mean()), 4) if (a.risk_level == lvl).any() else None}
               for lvl in LEVELS}
    return {"as_of_points": sorted({p["as_of"] for p in points}), "window_months": w, "min_next_reviews": C.RISK_BACKTEST_MIN_NEXT,
            "points": points, "summary": summary}


def products_table(clean: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Bảng PRODUCT (ERD): thống kê toàn kỳ + cửa sổ rủi ro + điều kiện dự báo theo sản phẩm."""
    g = clean.score.groupby(clean.product_id)
    base = pd.DataFrame({"n_reviews": g.size(), "avg_score": g.mean(),
                         "neg_rate": clean.sentiment.eq("neg").groupby(clean.product_id).mean(),
                         "first_month": clean.year_month.groupby(clean.product_id).min(),
                         "last_month": clean.year_month.groupby(clean.product_id).max()})
    upto = clean[clean.year_month <= as_of]
    base["n_active_months"] = upto.year_month.groupby(upto.product_id).nunique().reindex(base.index).fillna(0).astype(int)
    base["forecastable"] = base.n_active_months >= C.PRODUCT_FORECAST_MIN_MONTHS
    risk = compute_risk(clean, as_of).set_index("product_id")
    out = base.join(risk, how="left")
    out[["n_3m", "n_prev_3m"]] = out[["n_3m", "n_prev_3m"]].fillna(0).astype(int)
    out["risk_level"] = out.risk_level.fillna("insufficient")
    out["reason"] = out.reason.fillna("")
    out["signal"] = out.signal.fillna("")
    out["as_of"] = as_of
    out["risk_rank"] = out.risk_level.map(RISK_RANK)
    for c in ["avg_score", "neg_rate", "avg_3m", "neg_rate_3m", "avg_prev_3m", "delta"]:
        out[c] = out[c].astype(float).round(4)
    return out.reset_index().rename(columns={"index": "product_id"})
