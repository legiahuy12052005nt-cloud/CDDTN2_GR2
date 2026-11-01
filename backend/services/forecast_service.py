"""ForecastService – chỉ số hài lòng theo tháng và dự báo (FR-19, FR-20, NFR-04). Thiết kế theo notebook 04.

- Toàn bộ dữ liệu: ETS(A,Ad,N) (Holt giảm chấn) trên điểm TB tháng; chỉ dùng tháng có đủ đánh giá
  (ngưỡng monthly_threshold) và bỏ tháng chưa trọn cuối cùng; kiểm tra 12 tháng cuối so với mô hình ngây thơ.
- Từng sản phẩm: cần ≥ 36 tháng có đánh giá; làm trơn mũ ARIMA(0,1,1) chịu được tháng trống; độ tin cậy thấp.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.statespace.sarimax import SARIMAX

from backend.core import config as C
from backend.core.errors import ApiError
from backend.services.eda_service import group_stats

warnings.filterwarnings("ignore")


def monthly(df: pd.DataFrame, product_id: str | None = None) -> pd.DataFrame:
    d = df if not product_id else df[df.product_id == product_id]
    g = group_stats(d, "year_month")
    g["sat_index"] = C.satisfaction_index(g.avg_score)
    return g.rename(columns={"year_month": "month"})


def _points(g: pd.DataFrame) -> list[dict]:
    return [{"month": r.month, "n": int(r.n), "avg_score": round(float(r.avg_score), 4), "neg_rate": round(float(r.neg_rate), 4),
             "sat_index": round(float(r.sat_index), 2)} for r in g.itertuples()]


def _overall_series(df: pd.DataFrame, last_full: str) -> tuple[pd.Series, int]:
    g = monthly(df).set_index("month")
    g = g[g.index <= last_full]
    # tháng không có đánh giá nào không xuất hiện trong bảng gộp: điền n = 0 để bị coi là “không đạt ngưỡng”,
    # nếu không asfreq("MS") sẽ chèn NaN vào giữa chuỗi → ETS trả NaN → API #16 lỗi 500 khi trả JSON
    full = pd.period_range(g.index.min(), g.index.max(), freq="M").strftime("%Y-%m")
    g = g.reindex(full)
    g["n"] = g.n.fillna(0)
    T = C.monthly_threshold(len(df))
    ok = g.n >= T
    # tháng bắt đầu: sau tháng cuối cùng không đạt ngưỡng
    bad = np.where(~ok.values)[0]
    start = bad[-1] + 1 if len(bad) else 0
    s = g.avg_score.iloc[start:]
    s.index = pd.PeriodIndex(s.index, freq="M").to_timestamp()
    return s.asfreq("MS"), T


def _ets_forecast(s: pd.Series, h: int):
    if len(s) >= 24:
        m = ETSModel(s, error="add", trend="add", damped_trend=True).fit(disp=False)
        name = "ETS(A,Ad,N)"
    else:
        m = ETSModel(s, error="add").fit(disp=False); name = "ETS(A,N,N)"
    pf = m.get_prediction(start=len(s), end=len(s) + h - 1).summary_frame(alpha=0.05)
    return name, pf["mean"].values, pf["pi_lower"].values, pf["pi_upper"].values


def precompute(df: pd.DataFrame, last_full: str) -> dict:
    s, T = _overall_series(df, last_full)
    out = {"threshold_per_month": T, "series_start": s.index[0].strftime("%Y-%m") if len(s) else None,
           "series_end": s.index[-1].strftime("%Y-%m") if len(s) else None, "n_months": int(len(s))}
    if len(s) < 6:
        out.update({"model": None, "forecast": [], "backtest": None}); return out
    if len(s) >= 36:
        tr, te = s.iloc[:-12], s.iloc[-12:]
        name, mean, lo, hi = _ets_forecast(tr, 12)
        mae_m = float(np.mean(np.abs(te.values - mean))); mae_n = float(np.mean(np.abs(te.values - tr.iloc[-1])))
        out["backtest"] = {"mae_model": round(mae_m * 25, 2), "mae_naive": round(mae_n * 25, 2), "unit": "điểm chỉ số",
                           "test_from": te.index[0].strftime("%Y-%m"), "test_to": te.index[-1].strftime("%Y-%m")}
    else:
        out["backtest"] = None
    name, mean, lo, hi = _ets_forecast(s, 12)
    months = pd.period_range(pd.Period(out["series_end"], "M") + 1, periods=12, freq="M").strftime("%Y-%m")
    out["model"] = name
    out["forecast"] = [{"month": m, "sat_index": round(float(C.satisfaction_index(a)), 2), "lo": round(float(max(0, C.satisfaction_index(b))), 2),
                        "hi": round(float(min(100, C.satisfaction_index(c))), 2)} for m, a, b, c in zip(months, mean, lo, hi)]
    return out


def product_forecast(df: pd.DataFrame, product_id: str, last_full: str, months: int) -> dict:
    g = monthly(df, product_id)
    g = g[g.month <= last_full]
    hist = _points(g.tail(36))
    if len(g) < C.PRODUCT_FORECAST_MIN_MONTHS:
        return {"eligible": False, "message": f"Không đủ dữ liệu để dự báo (cần ≥ {C.PRODUCT_FORECAST_MIN_MONTHS} tháng có đánh giá, sản phẩm này có {len(g)} tháng)",
                "model": None, "history": hist, "forecast": [], "backtest": None}
    idx = pd.period_range(g.month.min(), last_full, freq="M")
    ser = g.set_index(pd.PeriodIndex(g.month, freq="M")).avg_score.reindex(idx)
    y = ser.values.astype(float)
    bt = None
    try:
        tr = y[:-12]; te_idx = ~np.isnan(y[-12:])
        if np.isfinite(tr).sum() >= 24 and te_idx.sum() >= 3:
            fc = SARIMAX(tr, order=(0, 1, 1)).fit(disp=False).forecast(12)
            last = tr[np.isfinite(tr)][-1]
            bt = {"mae_model": round(float(np.mean(np.abs(y[-12:][te_idx] - fc[te_idx]))) * 25, 2),
                  "mae_naive": round(float(np.mean(np.abs(y[-12:][te_idx] - last))) * 25, 2), "unit": "điểm chỉ số"}
        res = SARIMAX(y, order=(0, 1, 1)).fit(disp=False).get_forecast(months)
        mean = res.predicted_mean; ci = res.conf_int(alpha=0.05)
    except Exception:  # noqa: BLE001 – chuỗi quá nhiễu: dùng trung bình 12 tháng gần nhất
        base = np.nanmean(y[-12:]); mean = np.repeat(base, months); sd = np.nanstd(y[-12:]) or 0.5
        ci = np.c_[mean - 1.96 * sd, mean + 1.96 * sd]
    fm = pd.period_range(pd.Period(last_full, "M") + 1, periods=months, freq="M").strftime("%Y-%m")
    fc = [{"month": m, "sat_index": round(float(np.clip(C.satisfaction_index(a), 0, 100)), 2),
           "lo": round(float(np.clip(C.satisfaction_index(b), 0, 100)), 2), "hi": round(float(np.clip(C.satisfaction_index(c), 0, 100)), 2)}
          for m, a, b, c in zip(fm, mean, ci[:, 0], ci[:, 1])]
    return {"eligible": True, "message": "Dự báo theo sản phẩm có độ tin cậy thấp: mỗi tháng chỉ có ít đánh giá, hãy đọc cùng khoảng tin cậy",
            "model": "ARIMA(0,1,1) – làm trơn mũ", "history": hist, "forecast": fc, "backtest": bt}


def forecast(state, product_id: str | None, months: int) -> dict:
    last_full = state.meta.get("last_full_month")
    if product_id:
        key = (product_id, months)
        if key not in state.forecast_cache:
            state.forecast_cache[key] = product_forecast(state.df, product_id, last_full, months)
        r = state.forecast_cache[key]
        return {"meta": state.meta_block({"product_id": product_id}), "scope": "product", "product_id": product_id, **r}
    fo = state.forecast or {}
    g = monthly(state.df); g = g[(g.month <= last_full)]
    if fo.get("series_start"):
        g = g[g.month >= fo["series_start"]]
    return {"meta": state.meta_block(), "scope": "all", "product_id": None, "eligible": bool(fo.get("forecast")),
            "message": None if fo.get("forecast") else "Chuỗi theo tháng quá ngắn để dự báo",
            "model": fo.get("model"), "history": _points(g), "forecast": (fo.get("forecast") or [])[:months],
            "backtest": fo.get("backtest"), "series": {k: fo.get(k) for k in ["series_start", "series_end", "n_months", "threshold_per_month"]}}


def satisfaction(state, product_id: str | None, date_from: str | None, date_to: str | None) -> dict:
    if date_from and date_to and date_from > date_to:
        raise ApiError(422, "VALIDATION_ERROR", f"Khoảng thời gian không hợp lệ: từ tháng {date_from} sau đến tháng {date_to}")
    g = monthly(state.df, product_id)
    if date_from:
        g = g[g.month >= date_from]
    if date_to:
        g = g[g.month <= date_to]
    return {"meta": state.meta_block({"product_id": product_id, "date_from": date_from, "date_to": date_to}),
            "scope": "product" if product_id else "all", "product_id": product_id, "series": _points(g)}
