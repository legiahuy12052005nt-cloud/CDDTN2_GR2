# %% [markdown]
# # 01 – Phân tích khám phá dữ liệu (EDA) – Amazon Fine Food Reviews
# Buổi 5 – Thiết kế chi tiết. Người thực hiện chính: Dương Diễm My.
# Mục tiêu: thống kê mô tả, phân phối, phát hiện giá trị thiếu/bất thường trên dữ liệu thật,
# từ đó chốt quy tắc làm sạch R1–R9 và các tham số thiết kế (chuỗi dự báo, ngưỡng cảnh báo).

# %%
import sys, time, json, hashlib, re
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from backend.core import config as C
from backend.services import data_service as DS
import vizstyle as V
V.apply()
FIG = ROOT / "notebooks" / "figures"; FIG.mkdir(exist_ok=True)
OUT = ROOT / "notebooks" / "outputs"; OUT.mkdir(exist_ok=True)
stats = {}

# %% [markdown]
# ## 1. Nạp dữ liệu gốc và kiểm tra toàn vẹn

# %%
raw_path = C.DATA_RAW / "Reviews.csv"
md5 = hashlib.md5(raw_path.read_bytes()).hexdigest()
t0 = time.time(); raw = pd.read_csv(raw_path); t_read = time.time() - t0
stats["raw"] = {"md5": md5, "md5_expected": "c3c950ae0be8b0736477c89d052d33fd",
                "n_rows": len(raw), "n_cols": raw.shape[1], "read_seconds": round(t_read, 1),
                "memory_mb": round(raw.memory_usage(deep=True).sum() / 1e6)}
print(stats["raw"]); print(raw.dtypes)

# %%
schema = DS.validate_schema(raw); print(schema)
q = DS.quality_report(raw)
stats["quality"] = {k: q[k] for k in ["n_rows", "n_duplicates", "missing_by_column", "time_min", "time_max", "n_helpfulness_invalid"]}
stats["quality"]

# %% [markdown]
# ## 2. Thống kê mô tả các cột số trên dữ liệu gốc

# %%
desc = raw[["HelpfulnessNumerator", "HelpfulnessDenominator", "Score"]].describe().T.round(2)
stats["describe_raw"] = desc.to_dict("index"); desc

# %%
raw_scores = raw.Score.value_counts().sort_index()
stats["score_raw"] = {int(k): int(v) for k, v in raw_scores.items()}
key = C.DEDUP_KEYS
grp = raw.groupby(key, sort=False).Id.transform("size")
gs = raw.groupby(key, sort=False).size()
stats["duplicates"] = {
    "rows_duplicate": int(raw.duplicated(key).sum()),
    "rows_in_groups": int((grp > 1).sum()),
    "groups_gt1": int((gs > 1).sum()),
    "same_product_dup": int(raw.duplicated(key + ["ProductId"]).sum()),
    "group_size_counts": {int(k): int(v) for k, v in gs.value_counts().sort_index().items()},
    "groups_score_inconsistent": int((raw.groupby(key, sort=False).Score.nunique() > 1).sum()),
}
# Rò rỉ dữ liệu nếu tách train/test ngẫu nhiên trước khi bỏ trùng
rng = np.random.RandomState(C.RANDOM_STATE); m = rng.rand(len(raw)) < 0.8
tr = pd.MultiIndex.from_frame(raw.loc[m, key]); te = pd.MultiIndex.from_frame(raw.loc[~m, key])
stats["duplicates"]["leak_share_if_no_dedup"] = round(float(te.isin(tr).mean()), 4)
stats["duplicates"]

# %% [markdown]
# ## 3. Làm sạch theo quy tắc R1–R9 và lưu dữ liệu trung gian

# %%
t0 = time.time(); clean, log = DS.clean_reviews(raw); t_clean = time.time() - t0
meta = DS.dataset_meta(clean)
t0 = time.time(); clean.to_csv(C.DATA_PROCESSED / "reviews_clean.csv", index=False); t_save = time.time() - t0
stats["clean_log"] = log; stats["meta"] = meta
stats["timing"] = {"clean_seconds": round(t_clean, 1), "save_seconds": round(t_save, 1),
                   "file_mb": round((C.DATA_PROCESSED / "reviews_clean.csv").stat().st_size / 1e6)}
print(log, meta, stats["timing"])

# %% [markdown]
# ## 4. Phân bố số sao và nhãn cảm xúc (sau làm sạch)

# %%
sc = clean.score.value_counts().sort_index(); sn = clean.sentiment.value_counts()
stats["score_clean"] = {int(k): int(v) for k, v in sc.items()}
stats["sentiment_clean"] = {k: int(v) for k, v in sn.items()}
stats["score_mean_clean"] = round(float(clean.score.mean()), 4)
fig, ax = plt.subplots(figsize=(6.4, 2.8))
cols = [V.RED, V.RED, V.GRAY, V.BLUE, V.BLUE]
bars = ax.bar([f"{i} sao" for i in sc.index], sc.values, color=cols, width=0.62)
for b, v in zip(bars, sc.values):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v/len(clean):.1%}".replace(".", ","), ha="center", va="bottom", fontsize=8, color=V.INK2)
ax.yaxis.set_major_formatter(FuncFormatter(V.thousands)); ax.grid(axis="x", visible=False)
ax.set_title("Phân bố số sao sau làm sạch (n = %s)" % V.thousands(len(clean)))
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=V.RED, label="Tiêu cực (1–2 sao)"), Patch(color=V.GRAY, label="Trung tính (3 sao)"),
                   Patch(color=V.BLUE, label="Tích cực (4–5 sao)")], loc="upper left")
V.save(fig, FIG / "eda_01_score_dist.png")

# %% [markdown]
# ## 5. Diễn biến theo tháng: số đánh giá, điểm trung bình, tỷ lệ tiêu cực

# %%
mon = clean.groupby("year_month").agg(n=("score", "size"), avg=("score", "mean"),
                                       neg=("sentiment", lambda s: (s == "neg").mean()))
mon.to_csv(OUT / "monthly_overall.csv")
yr = clean.assign(y=clean.year_month.str[:4]).groupby("y").agg(n=("score", "size"), avg=("score", "mean"),
                                                               neg=("sentiment", lambda s: (s == "neg").mean()))
stats["by_year"] = yr.round(4).to_dict("index")
sub = mon.loc["2004-01":]
x = pd.to_datetime(sub.index)
fig, axs = plt.subplots(3, 1, figsize=(7.2, 6.2), sharex=True, gridspec_kw={"hspace": 0.35})
axs[0].bar(x, sub.n, width=25, color=[V.BLUE] * (len(sub) - 1) + [V.GRAY]); axs[0].set_title("a) Số đánh giá mỗi tháng")
axs[0].yaxis.set_major_formatter(FuncFormatter(V.thousands))
axs[1].plot(x, sub.avg, color=V.BLUE); axs[1].set_title("b) Điểm sao trung bình theo tháng")
axs[2].plot(x, sub.neg * 100, color=V.RED); axs[2].set_title("c) Tỷ lệ đánh giá tiêu cực theo tháng (%)")
for a in axs:
    a.axvspan(pd.Timestamp("2004-01-01"), pd.Timestamp("2006-12-31"), color="#f3f2ef", zorder=0)
axs[0].annotate("Trước 2007: < 700 đánh giá/tháng\n→ không đưa vào chuỗi dự báo", xy=(pd.Timestamp("2005-06-01"), sub.n.max() * 0.55),
                fontsize=7.5, color=V.INK2, ha="center")
axs[0].annotate("10/2012 (xám): chỉ có dữ liệu đến ngày 26", xy=(pd.Timestamp("2012-10-15"), sub.n.iloc[-1]),
                xytext=(pd.Timestamp("2008-01-01"), sub.n.max() * 0.8), fontsize=7.5, color=V.INK2,
                arrowprops=dict(arrowstyle="->", color=V.INK2, lw=0.8))
V.save(fig, FIG / "eda_02_monthly.png")
stats["monthly_threshold"] = {"first_month_all_ge_700": next(m for m in mon.index if (mon.loc[m:].n.iloc[:-1] >= C.FORECAST_MIN_REVIEWS_PER_MONTH).all()),
                              "n_2012_09": int(mon.loc["2012-09", "n"]), "n_2012_10": int(mon.loc["2012-10", "n"])}
stats["monthly_threshold"]

# %%
cal = clean[(clean.year_month >= "2007-01") & (clean.year_month <= meta["last_full_month"])]
stats["calendar_month_avg"] = cal.groupby(cal.year_month.str[5:]).score.mean().round(3).to_dict()
stats["calendar_month_avg"]

# %% [markdown]
# ## 6. Độ dài đánh giá

# %%
nw = clean.n_words
stats["n_words"] = {k: round(float(v), 1) for k, v in nw.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99]).items()}
stats["n_words_by_score_median"] = clean.groupby("score").n_words.median().to_dict()
stats["n_words_gt_1000"] = int((nw > 1000).sum())
stats["html"] = {"share_tag": round(float(raw.Text.str.contains(r"<[^>]+>", regex=True).mean()), 4),
                 "share_br": round(float(raw.Text.str.contains("<br", regex=False).mean()), 4),
                 "share_link": round(float(raw.Text.str.contains("<a href", regex=False).mean()), 4),
                 "share_entity": round(float(raw.Text.str.contains(r"&[a-z]+;|&#\d+;", regex=True).mean()), 4)}
fig, ax = plt.subplots(figsize=(6.4, 2.8))
data = [clean.loc[clean.score == s, "n_words"].values for s in range(1, 6)]
bp = ax.boxplot(data, showfliers=False, widths=0.5, patch_artist=True, medianprops=dict(color=V.INK, lw=1.5))
for p, c in zip(bp["boxes"], cols): p.set_facecolor(c); p.set_alpha(0.85); p.set_edgecolor("white")
ax.set_xticklabels([f"{i} sao" for i in range(1, 6)]); ax.set_ylabel("Số từ / đánh giá"); ax.grid(axis="x", visible=False)
ax.set_title("Độ dài đánh giá theo số sao (hộp: Q1–Q3, vạch: trung vị)")
V.save(fig, FIG / "eda_03_length.png")
stats["n_words"], stats["n_words_by_score_median"], stats["html"]

# %% [markdown]
# ## 7. Sản phẩm và người dùng – phân phối đuôi dài

# %%
p = clean.product_id.value_counts(); u = clean.user_key.value_counts()
bins = [(1, 1, "1"), (2, 4, "2–4"), (5, 9, "5–9"), (10, 19, "10–19"), (20, 49, "20–49"), (50, 99, "50–99"), (100, 10**6, "≥ 100")]
pb = pd.DataFrame([{"nhom": l, "san_pham": int(((p >= a) & (p <= b)).sum()), "danh_gia": int(p[(p >= a) & (p <= b)].sum())} for a, b, l in bins])
pb.to_csv(OUT / "product_buckets.csv", index=False)
stats["products"] = {"n": int(len(p)), "median_reviews": float(p.median()), "mean_reviews": round(float(p.mean()), 2),
                     "max_reviews": int(p.max()), "ge5": int((p >= 5).sum()), "ge10": int((p >= 10).sum()), "ge100": int((p >= 100).sum()),
                     "share_reviews_ge10": round(float(p[p >= 10].sum() / len(clean)), 4), "buckets": pb.to_dict("records"),
                     "top10": {k: int(v) for k, v in p.head(10).items()}}
stats["users"] = {"n": int(len(u)), "share_one_review": round(float((u == 1).mean()), 4), "max_reviews": int(u.max()), "gt50": int((u > 50).sum())}
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"wspace": 0.35})
axs[0].bar(pb.nhom, pb.san_pham, color=V.BLUE, width=0.62); axs[0].set_title("a) Số sản phẩm theo số đánh giá")
axs[1].bar(pb.nhom, pb.danh_gia / len(clean) * 100, color=V.BLUE, width=0.62); axs[1].set_title("b) Tỷ trọng đánh giá (%)")
for a in axs:
    a.grid(axis="x", visible=False); a.tick_params(axis="x", rotation=0, labelsize=7); a.set_xlabel("Số đánh giá của sản phẩm")
axs[0].yaxis.set_major_formatter(FuncFormatter(V.thousands))
V.save(fig, FIG / "eda_04_products.png")
stats["products"], stats["users"]

# %%
pm = clean.groupby(["product_id", "year_month"]).size()
months_per_product = pm.groupby(level=0).size()
stats["forecast_eligibility"] = {f"ge{k}_months": int((months_per_product >= k).sum()) for k in [12, 24, 36, 48]}
stats["forecast_eligibility"]

# %% [markdown]
# ## 8. Mức độ hữu ích (helpfulness) theo số sao

# %%
h = clean[clean.helpful_den > 0]
stats["helpfulness"] = {"share_has_votes": round(len(h) / len(clean), 4),
                        "ratio_by_score": h.groupby("score").helpful_ratio.mean().round(3).to_dict(),
                        "den_p99": float(clean.helpful_den.quantile(.99)), "den_max": int(clean.helpful_den.max())}
stats["helpfulness"]

# %% [markdown]
# ## 9. Bất thường khác: ngôn ngữ khác tiếng Anh, văn bản trùng giữa nhiều người dùng

# %%
SW = set("the and to of a i it is this in for that was my with but have not you are they on as so be".split())
def stop_ratio(t):
    w = re.findall(r"[a-z']+", t.lower()); return 0 if not w else sum(x in SW for x in w) / len(w)
smp = clean.text.sample(50_000, random_state=C.RANDOM_STATE).map(stop_ratio)
tx = clean.groupby("text").user_key.nunique()
stats["anomalies"] = {"non_english_share_est": round(float((smp < 0.1).mean()), 4),
                      "texts_shared_by_users": int((tx > 1).sum()),
                      "rows_texts_shared": int(clean.text.isin(tx[tx > 1].index).sum()),
                      "summary_missing_raw": int(raw.Summary.isna().sum()), "profile_missing_raw": int(raw.ProfileName.isna().sum()),
                      "year_lt_2004_rows": int((clean.year_month < "2004-01").sum())}
stats["anomalies"]

# %% [markdown]
# ## 10. Từ khóa đặc trưng của nhóm Tiêu cực và Tích cực (log-odds, prior Dirichlet)

# %%
stop = sorted(ENGLISH_STOP_WORDS - {"not", "no", "nor", "never", "too", "very"} | {"br", "amazon", "product", "products", "just", "like", "really", "got"})
smp = clean[clean.sentiment != "neu"].sample(150_000, random_state=C.RANDOM_STATE)
cv = CountVectorizer(preprocessor=DS.model_preprocess, stop_words=stop, ngram_range=(1, 2), min_df=30, max_features=40_000)
X = cv.fit_transform(smp.text); vocab = np.array(cv.get_feature_names_out())
neg = np.asarray(X[(smp.sentiment == "neg").values].sum(0)).ravel(); pos = np.asarray(X[(smp.sentiment == "pos").values].sum(0)).ravel()
a0 = neg + pos; a = a0 / a0.sum() * 1000  # prior
ni, nj, a_sum = neg.sum(), pos.sum(), a.sum()
d = np.log((neg + a) / (ni + a_sum - neg - a)) - np.log((pos + a) / (nj + a_sum - pos - a))
z = d / np.sqrt(1 / (neg + a) + 1 / (pos + a))
top_neg = pd.Series(z, vocab).sort_values(ascending=False).head(15)
top_pos = pd.Series(-z, vocab).sort_values(ascending=False).head(15)
stats["keywords"] = {"neg": top_neg.round(1).to_dict(), "pos": top_pos.round(1).to_dict()}
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.6), gridspec_kw={"wspace": 0.55})
axs[0].barh(top_neg.index[::-1], top_neg.values[::-1], color=V.RED, height=0.62); axs[0].set_title("a) Đặc trưng nhóm Tiêu cực")
axs[1].barh(top_pos.index[::-1], top_pos.values[::-1], color=V.BLUE, height=0.62); axs[1].set_title("b) Đặc trưng nhóm Tích cực")
for ax_ in axs: ax_.grid(axis="y", visible=False); ax_.set_xlabel("z-score log-odds"); ax_.tick_params(axis="y", labelsize=7.5)
V.save(fig, FIG / "eda_05_keywords.png")
stats["keywords"]

# %%
def _clean_json(o):
    if isinstance(o, dict): return {str(k): _clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean_json(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    return o
(OUT / "eda_stats.json").write_text(json.dumps(_clean_json(stats), ensure_ascii=False, indent=1), encoding="utf-8")
print("Đã lưu eda_stats.json")
