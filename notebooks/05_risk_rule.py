# %% [markdown]
# # 05 – Chốt ngưỡng cảnh báo sản phẩm (FR-21) và kiểm tra ngược (backtest)
# Buổi 5 – Thiết kế chi tiết. Người thực hiện chính: Nguyễn Hoàng Thuận.
# FR-21 trong SRS để ngưỡng "chốt sau EDA". Notebook này: (1) xem phân bố Δ điểm 3 tháng và tỷ lệ tiêu cực
# của các sản phẩm đủ dữ liệu; (2) chọn ngưỡng theo phân vị; (3) kiểm tra ngược xem nhóm "Cao" có thật sự
# tiếp tục kém hơn ở 3 tháng sau hay không.

# %%
import sys, json
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from backend.core import config as C
from backend.services.alert_service import compute_risk
import vizstyle as V
V.apply()
FIG = ROOT / "notebooks" / "figures"; OUT = ROOT / "notebooks" / "outputs"
K = {}
df = pd.read_csv(C.DATA_PROCESSED / "reviews_clean.csv", usecols=["product_id", "score", "sentiment", "year_month"])

# %% [markdown]
# ## 1. Phân bố tín hiệu trên các sản phẩm đủ dữ liệu (≥ 10 đánh giá mỗi cửa sổ), tính đến 09/2012

# %%
r = compute_risk(df, "2012-09"); e = r[r.risk_level != "insufficient"]
K["eligible"] = len(e); K["active_products_3m"] = int((r.n_3m > 0).sum())
K["delta_pct"] = e.delta.quantile([.05, .1, .25, .5, .75, .9]).round(3).to_dict()
K["neg_pct"] = e.neg_rate_3m.quantile([.5, .75, .9, .95]).round(3).to_dict()
K["overall_neg_rate_3m"] = round(float((df[df.year_month.between("2012-07", "2012-09")].sentiment == "neg").mean()), 4)
K["levels_2012_09"] = e.risk_level.value_counts().to_dict()
K["delta_pct"], K["neg_pct"], K["levels_2012_09"], K["overall_neg_rate_3m"]

# %%
r.to_csv(C.DATA_PROCESSED / "product_risk.csv", index=False)
top = e.sort_values(["risk_level", "delta"], key=lambda s: s.map({"high": 0, "medium": 1, "low": 2}) if s.name == "risk_level" else s).head(8)
K["top_high"] = top[["product_id", "n_3m", "avg_3m", "neg_rate_3m", "n_prev_3m", "avg_prev_3m", "delta", "risk_level", "reason"]].round(3).to_dict("records")
pd.DataFrame(K["top_high"])

# %%
fig, ax = plt.subplots(figsize=(6.6, 3.4))
col = e.risk_level.map({"high": V.RED, "medium": V.YELLOW, "low": V.BLUE})
ax.scatter(e.delta, e.neg_rate_3m * 100, s=np.clip(e.n_3m, 10, 80), c=col, alpha=0.75, edgecolor="white", linewidth=0.6)
ax.axvline(C.RISK_HIGH_DELTA, color=V.RED, ls="--", lw=1); ax.axvline(C.RISK_MID_DELTA, color=V.YELLOW, ls="--", lw=1)
ax.axhline(C.RISK_HIGH_NEG * 100, color=V.RED, ls="--", lw=1); ax.axhline(C.RISK_MID_NEG * 100, color=V.YELLOW, ls="--", lw=1)
ax.set_xlabel("Δ điểm TB: 3 tháng gần nhất − 3 tháng trước (sao)"); ax.set_ylabel("Tỷ lệ tiêu cực 3 tháng gần nhất (%)")
ax.set_title(f"Sản phẩm đủ dữ liệu tại 09/2012 (n = {len(e)}); kích thước điểm = số đánh giá")
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", ls="", color=c, label=l) for c, l in [(V.RED, "Cao"), (V.YELLOW, "Trung bình"), (V.BLUE, "Thấp")]],
          loc="upper right", title="Mức rủi ro", title_fontsize=8)
V.save(fig, FIG / "risk_01_scatter.png")

# %% [markdown]
# ## 2. Kiểm tra ngược: gắn mức rủi ro tại một tháng, xem 3 tháng tiếp theo

# %%
bt = []
for asof, nxt in [("2012-03", ("2012-04", "2012-06")), ("2012-06", ("2012-07", "2012-09"))]:
    rr = compute_risk(df, asof); rr = rr[rr.risk_level != "insufficient"].set_index("product_id")
    f = df[df.year_month.between(*nxt)].groupby("product_id").agg(n_next=("score", "size"), avg_next=("score", "mean"),
                                                                   neg_next=("sentiment", lambda s: (s == "neg").mean()))
    j = rr.join(f, how="inner"); j = j[j.n_next >= 5]
    g = j.groupby("risk_level").agg(san_pham=("n_next", "size"), neg_now=("neg_rate_3m", "mean"), neg_next=("neg_next", "mean"),
                                    avg_now=("avg_3m", "mean"), avg_next=("avg_next", "mean")).reindex(["high", "medium", "low"])
    g["as_of"] = asof; bt.append(g.reset_index())
bt = pd.concat(bt); bt.round(3).to_csv(OUT / "risk_backtest.csv", index=False)
K["backtest"] = bt.round(3).to_dict("records")
bt.round(3)

# %%
(OUT / "risk_results.json").write_text(json.dumps(K, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(json.dumps(K, ensure_ascii=False, indent=1, default=float)[:3000])
