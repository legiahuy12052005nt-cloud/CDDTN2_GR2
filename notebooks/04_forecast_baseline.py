# %% [markdown]
# # 04 – Thiết kế thực nghiệm và baseline dự báo mức độ hài lòng (FR-19, FR-20, NFR-04)
# Buổi 5 – Thiết kế chi tiết. Người thực hiện chính: Nguyễn Hoàng Thuận.
# Chuỗi: điểm sao trung bình theo tháng (quy đổi chỉ số hài lòng 0–100). Chỉ dùng tháng có ≥ 700 đánh giá
# (sai số chuẩn ≤ 0,05 sao) và bỏ tháng chưa trọn → 01/2007 – 09/2012 (69 tháng).
# Kiểm tra: giữ 12 tháng cuối (10/2011 – 09/2012), dự báo nhiều bước từ gốc 09/2011.

# %%
import sys, json, warnings
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.statespace.sarimax import SARIMAX
from backend.core import config as C
import vizstyle as V
V.apply(); warnings.filterwarnings("ignore")
FIG = ROOT / "notebooks" / "figures"; OUT = ROOT / "notebooks" / "outputs"
F = {}

# %%
df = pd.read_csv(C.DATA_PROCESSED / "reviews_clean.csv", usecols=["product_id", "score", "sentiment", "year_month"])
mon = df.groupby("year_month").agg(n=("score", "size"), avg=("score", "mean"), neg=("sentiment", lambda s: (s == "neg").mean()))
mon["sat_index"] = C.satisfaction_index(mon.avg)
mon.to_csv(C.DATA_PROCESSED / "monthly_metrics_overall.csv")
s = mon.loc["2007-01":"2012-09", "avg"]; s.index = pd.PeriodIndex(s.index, freq="M").to_timestamp()
s = s.asfreq("MS")
H = C.FORECAST_TEST_MONTHS; train, test = s.iloc[:-H], s.iloc[-H:]
F["series"] = {"start": "2007-01", "end": "2012-09", "n_months": len(s), "train": len(train), "test": len(test),
               "min_n_per_month": int(mon.loc["2007-01":"2012-09", "n"].min())}
F["series"]

# %% [markdown]
# ## Các mô hình so sánh trên 12 tháng kiểm tra

# %%
def mae(a, b): return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))
res, fc = [], {}
fc["Naive (giữ tháng trước)"] = np.repeat(train.iloc[-1], H)
fc["Seasonal naive (cùng tháng năm trước)"] = train.iloc[-12:].values
fc["Trung bình 12 tháng gần nhất"] = np.repeat(train.iloc[-12:].mean(), H)
slope = (train.iloc[-1] - train.iloc[0]) / (len(train) - 1)
fc["Drift (xu hướng tuyến tính)"] = train.iloc[-1] + slope * np.arange(1, H + 1)
ets = ETSModel(train, error="add", trend="add", damped_trend=True).fit(disp=False)
pe = ets.get_prediction(start=len(train), end=len(train) + H - 1).summary_frame(alpha=0.05)
fc["ETS(A,Ad,N) – Holt giảm chấn"] = pe["mean"].values; ci = {"ETS(A,Ad,N) – Holt giảm chấn": pe[["pi_lower", "pi_upper"]].values}
ets_s = ETSModel(train, error="add", trend="add", damped_trend=True, seasonal="add", seasonal_periods=12).fit(disp=False)
pes = ets_s.get_prediction(start=len(train), end=len(train) + H - 1).summary_frame(alpha=0.05)
fc["ETS(A,Ad,A) – có mùa vụ 12 tháng"] = pes["mean"].values; ci["ETS(A,Ad,A) – có mùa vụ 12 tháng"] = pes[["pi_lower", "pi_upper"]].values
best_aic, best_order = np.inf, None
for p in range(3):
    for q in range(3):
        try:
            m = SARIMAX(train, order=(p, 1, q), trend="n").fit(disp=False)
            if m.aic < best_aic: best_aic, best_order = m.aic, (p, 1, q)
        except Exception:
            pass
sar = SARIMAX(train, order=best_order).fit(disp=False); ps = sar.get_forecast(H)
name_sar = f"ARIMA{best_order} – chọn theo AIC"
fc[name_sar] = ps.predicted_mean.values; ci[name_sar] = ps.conf_int(alpha=0.05).values
for k, v in fc.items():
    row = {"model": k, "mae_star": round(mae(test, v), 4), "mae_index": round(mae(test, v) * 25, 2),
           "rmse_star": round(float(np.sqrt(np.mean((test.values - v) ** 2))), 4)}
    if k in ci: row["coverage95"] = round(float(np.mean((test.values >= ci[k][:, 0]) & (test.values <= ci[k][:, 1]))), 3)
    res.append(row)
res = pd.DataFrame(res).sort_values("mae_star"); res.to_csv(OUT / "forecast_holdout.csv", index=False)
F["holdout"] = res.to_dict("records"); F["arima_order"] = best_order
naive = res.loc[res.model.str.startswith("Naive"), "mae_star"].iloc[0]
F["best_model"] = res.iloc[0].model; F["beats_naive"] = bool(res.iloc[0].mae_star < naive)
F["ets_params"] = {k: round(float(v), 4) for k, v in zip(ets.param_names, np.asarray(ets.params))}
res

# %% [markdown]
# ## Đánh giá cuộn 1 bước (rolling origin) – kiểm tra độ ổn định

# %%
roll = {"Naive": [], "ETS(A,Ad,N)": [], name_sar: []}
for i in range(H):
    tr = s.iloc[: len(train) + i]; actual = s.iloc[len(train) + i]
    roll["Naive"].append(abs(actual - tr.iloc[-1]))
    roll["ETS(A,Ad,N)"].append(abs(actual - ETSModel(tr, error="add", trend="add", damped_trend=True).fit(disp=False).forecast(1).iloc[0]))
    roll[name_sar].append(abs(actual - SARIMAX(tr, order=best_order).fit(disp=False).forecast(1).iloc[0]))
F["rolling_1step_mae"] = {k: round(float(np.mean(v)), 4) for k, v in roll.items()}
F["rolling_1step_mae"]

# %% [markdown]
# ## Dự báo chính thức 12 tháng tới (huấn luyện lại trên toàn bộ 69 tháng)

# %%
best_name = F["best_model"]
if best_name.startswith("ETS(A,Ad,N)"):
    full = ETSModel(s, error="add", trend="add", damped_trend=True).fit(disp=False)
    pf = full.get_prediction(start=len(s), end=len(s) + 11).summary_frame(alpha=0.05).rename(columns={"pi_lower": "lo", "pi_upper": "hi"})
else:
    full = SARIMAX(s, order=best_order).fit(disp=False); g = full.get_forecast(12)
    pf = pd.DataFrame({"mean": g.predicted_mean, "lo": g.conf_int().iloc[:, 0], "hi": g.conf_int().iloc[:, 1]})
pf = pf[["mean", "lo", "hi"]]
out = pf.assign(sat_index=C.satisfaction_index(pf["mean"]), sat_lo=C.satisfaction_index(pf.lo), sat_hi=C.satisfaction_index(pf.hi))
out.index = out.index.strftime("%Y-%m"); out.round(4).to_csv(C.DATA_PROCESSED / "forecast_overall.csv")
F["forecast_12m"] = out.round(3).to_dict("index")
out.round(3)

# %%
fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.9), gridspec_kw={"wspace": 0.3, "width_ratios": [1.15, 1]})
ax = axs[0]
ax.plot(s.index[-36:], s.iloc[-36:].values, color=V.INK2, lw=1.6, label="Thực tế")
ax.axvspan(test.index[0], test.index[-1], color="#f3f2ef", zorder=0, label="12 tháng giữ lại")
ax.plot(test.index, fc["Naive (giữ tháng trước)"], color=V.GRAY, ls="--", lw=1.5, label="Naive")
ax.plot(test.index, fc["ETS(A,Ad,N) – Holt giảm chấn"], color=V.BLUE, lw=1.8, label="ETS(A,Ad,N)")
ax.plot(test.index, fc[name_sar], color=V.ORANGE, lw=1.8, label=f"ARIMA{best_order}")
ax.set_title("a) Kiểm tra trên 12 tháng giữ lại"); ax.set_ylabel("Điểm sao TB tháng"); ax.legend(loc="upper right", fontsize=6.5)
ax.tick_params(axis="x", rotation=30); ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.2f}".replace(".", ",")))
ax = axs[1]
hist = s.iloc[-24:]; fidx = pd.PeriodIndex(out.index, freq="M").to_timestamp()
ax.plot(hist.index, C.satisfaction_index(hist.values), color=V.INK2, lw=1.6, label="Thực tế")
ax.plot(fidx, out.sat_index, color=V.BLUE, lw=1.8, label="Dự báo")
ax.fill_between(fidx, out.sat_lo, out.sat_hi, color=V.BLUE, alpha=0.15, lw=0, label="Khoảng tin cậy 95%")
ax.set_title("b) Dự báo 12 tháng tới"); ax.set_ylabel("Chỉ số hài lòng 0–100"); ax.legend(loc="lower left", fontsize=6.5)
ax.tick_params(axis="x", rotation=30)
V.save(fig, FIG / "forecast_01_overall.png")

# %% [markdown]
# ## Dự báo theo từng sản phẩm: kiểm tra trên sản phẩm đủ điều kiện (≥ 36 tháng có đánh giá trong giai đoạn huấn luyện)

# %%
df["ym"] = pd.PeriodIndex(df.year_month, freq="M")
cut = pd.Period("2011-09", "M"); tst = pd.period_range("2011-10", "2012-09", freq="M")
pm = df[df.ym <= pd.Period("2012-09", "M")].groupby(["product_id", "ym"]).score.mean()
months_train = pm[pm.index.get_level_values(1) <= cut].groupby(level=0).size()
elig = months_train[months_train >= C.PRODUCT_FORECAST_MIN_MONTHS].index
rows = []
for pid in elig:
    ser = pm.loc[pid]; full_idx = pd.period_range(ser.index.min(), pd.Period("2012-09", "M"), freq="M")
    ser = ser.reindex(full_idx); tr = ser[ser.index <= cut]; te = ser[ser.index > cut].dropna()
    if len(te) < 3: continue
    last = tr.dropna().iloc[-1]; mean_all = tr.mean()
    try:
        m = SARIMAX(tr.values.astype(float), order=(0, 1, 1)).fit(disp=False)   # làm trơn mũ, chịu được tháng trống
        ses = m.forecast(len(tst)); ses = pd.Series(ses, index=tst).loc[te.index].values
    except Exception:
        ses = np.repeat(mean_all, len(te))
    rows.append({"product_id": pid, "n_test_months": len(te), "naive": mae(te, np.repeat(last, len(te))),
                 "mean_history": mae(te, np.repeat(mean_all, len(te))), "ses": mae(te, ses)})
pr = pd.DataFrame(rows); pr.to_csv(OUT / "forecast_product_backtest.csv", index=False)
F["product_backtest"] = {"n_products": len(pr), "mae_naive": round(pr.naive.mean(), 4), "mae_mean_history": round(pr.mean_history.mean(), 4),
                         "mae_ses": round(pr.ses.mean(), 4), "share_ses_beats_naive": round(float((pr.ses < pr.naive).mean()), 3)}
F["n_products_eligible_full"] = int((pm.groupby(level=0).size() >= C.PRODUCT_FORECAST_MIN_MONTHS).sum())
F["product_backtest"], F["n_products_eligible_full"]

# %% [markdown]
# ## Làm trơn mũ so với trung bình lịch sử: chênh lệch có ý nghĩa thống kê không?
# Trung bình lịch sử có MAE trung bình thấp hơn một chút. Kiểm định Wilcoxon cặp đôi (cùng sản phẩm) và khoảng tin cậy
# bootstrap 95% của chênh lệch MAE cho biết chênh lệch này có thật hay chỉ do nhiễu – căn cứ cho quyết định FR-20 (mục 5.4).

# %%
from scipy.stats import wilcoxon
diff = pr.ses - pr.mean_history                                   # > 0: làm trơn mũ sai số lớn hơn
rng = np.random.default_rng(C.RANDOM_STATE)
boot = [rng.choice(diff.values, len(diff)).mean() for _ in range(5000)]
F["product_backtest_test"] = {"mean_diff_ses_minus_mean": round(float(diff.mean()), 4),
                              "bootstrap_ci95": [round(float(x), 4) for x in np.percentile(boot, [2.5, 97.5])],
                              "wilcoxon_p": round(float(wilcoxon(pr.ses, pr.mean_history).pvalue), 3),
                              "share_ses_beats_mean": round(float((pr.ses < pr.mean_history).mean()), 3)}
F["product_backtest_test"]

# %%
(OUT / "forecast_results.json").write_text(json.dumps(F, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: F[k] for k in ["series", "holdout", "best_model", "beats_naive", "rolling_1step_mae", "product_backtest"]}, ensure_ascii=False, indent=1, default=str))
