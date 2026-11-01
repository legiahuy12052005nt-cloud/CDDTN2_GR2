# %% [markdown]
# # 03 – Thiết kế thực nghiệm và baseline mô hình chủ đề phàn nàn (FR-18)
# Buổi 5 – Thiết kế chi tiết. Người thực hiện chính: KAYSONE Souk Anong.
# Dữ liệu: đánh giá Tiêu cực (1–2 sao) sau làm sạch. Baseline: TF-IDF + NMF, thử k = 5…12;
# chọn k theo độ mạch lạc NPMI (top-10 từ) và độ đa dạng chủ đề; đối chứng LDA tại k đã chọn.

# %%
import sys, time, json
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.decomposition import NMF, LatentDirichletAllocation
from backend.core import config as C
from backend.services import data_service as DS
import vizstyle as V
V.apply()
FIG = ROOT / "notebooks" / "figures"; OUT = ROOT / "notebooks" / "outputs"
T = {}

# %%
df = pd.read_csv(C.DATA_PROCESSED / "reviews_clean.csv", usecols=["review_id", "product_id", "score", "sentiment", "year_month", "summary", "text", "helpful_num"],
                 dtype={"summary": str, "text": str}, keep_default_na=False)
neg = df[df.sentiment == "neg"].reset_index(drop=True)
neg["doc"] = neg.summary + " . " + neg.text
T["n_docs"] = len(neg)
# Từ dừng: tiếng Anh + từ chung chung của đánh giá chê (không mang thông tin "chê về điều gì")
DOMAIN_STOP = {"br", "amazon", "product", "products", "item", "just", "like", "really", "would", "could", "one", "get", "got",
               "buy", "bought", "order", "ordered", "purchase", "purchased", "review", "reviews", "even", "also", "much", "think",
               "know", "way", "make", "made", "use", "used", "say", "said", "thing", "things", "time", "try", "tried", "good", "bad",
               "great", "better", "best", "disappointed", "disappointing", "terrible", "horrible", "awful", "worst", "not", "don",
               "didn", "doesn", "isn", "wasn", "ve", "ll", "re", "did", "does", "doing", "will", "going", "want", "wanted", "thought",
               "stars", "star", "recommend", "money", "waste", "never", "again", "back", "first", "well", "still", "since"}
STOP = sorted(set(ENGLISH_STOP_WORDS) | DOMAIN_STOP)
tf = TfidfVectorizer(preprocessor=DS.model_preprocess, stop_words=STOP, ngram_range=(1, 2), min_df=10, max_df=0.4, max_features=20_000, sublinear_tf=True)
X = tf.fit_transform(neg.doc); vocab = np.array(tf.get_feature_names_out())
B = (X > 0).astype(np.float32).tocsc()       # ma trận nhị phân để tính đồng xuất hiện
df_count = np.asarray(B.sum(0)).ravel(); N = B.shape[0]

def npmi(top_idx):
    s = []
    for a in range(len(top_idx)):
        for b in range(a + 1, len(top_idx)):
            i, j = top_idx[a], top_idx[b]
            co = B[:, i].multiply(B[:, j]).sum()
            if co == 0: s.append(-1.0); continue
            pij, pi, pj = co / N, df_count[i] / N, df_count[j] / N
            s.append(np.log(pij / (pi * pj)) / -np.log(pij))
    return float(np.mean(s))

# %% [markdown]
# ## Chọn số chủ đề k

# %%
rows, models = [], {}
for k in C.TOPIC_K_RANGE:
    t0 = time.time(); nmf = NMF(n_components=k, init="nndsvda", random_state=C.RANDOM_STATE, max_iter=400).fit(X)
    tops = [np.argsort(c)[::-1][:10] for c in nmf.components_]
    coh = np.mean([npmi(t) for t in tops]); div = len(set(np.concatenate(tops))) / (10 * k)
    rows.append({"k": k, "npmi": round(coh, 4), "diversity": round(div, 3), "sec": round(time.time() - t0, 1)}); models[k] = nmf
ksel = pd.DataFrame(rows); ksel.to_csv(OUT / "topic_k_selection.csv", index=False)
ok = ksel[ksel.diversity >= 0.8]
K = int(ok.loc[ok.npmi.idxmax(), "k"]); T["k_selection"] = rows; T["k_chosen"] = K
ksel, K

# %%
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.5), gridspec_kw={"wspace": 0.35})
axs[0].plot(ksel.k, ksel.npmi, marker="o", color=V.BLUE); axs[0].set_title("a) Độ mạch lạc NPMI (cao hơn tốt hơn)")
axs[1].plot(ksel.k, ksel.diversity, marker="o", color=V.AQUA); axs[1].axhline(0.8, color=V.ORANGE, ls="--", lw=1.2); axs[1].set_title("b) Độ đa dạng chủ đề (ngưỡng 0,8)")
for a in axs: a.axvline(K, color=V.GRAY, lw=1, ls=":"); a.set_xlabel("Số chủ đề k")
V.save(fig, FIG / "topic_01_k_selection.png")

# %% [markdown]
# ## Đối chứng LDA tại k đã chọn

# %%
cv = CountVectorizer(preprocessor=DS.model_preprocess, stop_words=STOP, ngram_range=(1, 2), min_df=10, max_df=0.4, max_features=20_000)
Xc = cv.fit_transform(neg.doc)
t0 = time.time(); lda = LatentDirichletAllocation(n_components=K, learning_method="online", batch_size=2048, random_state=C.RANDOM_STATE, max_iter=10).fit(Xc)
vc = {w: i for i, w in enumerate(vocab)}
lda_tops = [[vc[w] for w in np.array(cv.get_feature_names_out())[np.argsort(c)[::-1]] if w in vc][:10] for c in lda.components_]
T["lda_compare"] = {"npmi": round(np.mean([npmi(t) for t in lda_tops]), 4), "sec": round(time.time() - t0, 1),
                    "nmf_npmi": float(ksel.loc[ksel.k == K, "npmi"].iloc[0])}
T["lda_compare"]

# %% [markdown]
# ## Chủ đề của mô hình được chọn (NMF, k = K)

# %%
nmf = models[K]; W = nmf.transform(X); H = nmf.components_
top_words = [vocab[np.argsort(h)[::-1][:10]].tolist() for h in H]
for i, tw in enumerate(top_words): print(i, ", ".join(tw))

# %%
# Tên chủ đề do nhóm đặt sau khi đọc từ khóa và đánh giá mẫu (bước thủ công có kiểm tra chéo)
NAMES = json.loads((ROOT / "notebooks" / "topic_names.json").read_text(encoding="utf-8")) if (ROOT / "notebooks" / "topic_names.json").exists() else {}
dom = W.argmax(1); wmax = W.max(1)
neg["topic_id"] = np.where(wmax > 0, dom, -1); neg["topic_weight"] = wmax
topics = []
for i in range(K):
    d = neg[neg.topic_id == i]
    # đánh giá mẫu: trọng số chủ đề cao nhất trong nhóm có độ dài 25–120 từ (đủ thông tin, dễ đọc)
    ex = d.assign(L=d.text.str.split().str.len()).query("25 <= L <= 120").sort_values("topic_weight", ascending=False).head(3)
    topics.append({"topic_id": i, "name": NAMES.get(str(i), {}).get("name", f"Chủ đề {i}"), "name_en": NAMES.get(str(i), {}).get("en", ""),
                   "keywords": top_words[i], "n_reviews": int(len(d)), "share": round(len(d) / len(neg), 4),
                   "sample_review_ids": ex.review_id.tolist(), "sample_summaries": ex.summary.tolist()})
tp = pd.DataFrame(topics); tp.to_csv(C.DATA_PROCESSED / "topics.csv", index=False)
neg[["review_id", "topic_id", "topic_weight"]].to_csv(C.DATA_PROCESSED / "review_topics.csv", index=False)
T["topics"] = topics; T["no_topic"] = int((neg.topic_id == -1).sum())
tp[["topic_id", "name", "share", "keywords"]]

# %%
yr = neg[(neg.year_month >= "2008-01") & (neg.year_month <= "2012-09")].assign(y=lambda d: d.year_month.str[:4])
trend = (yr[yr.topic_id >= 0].groupby(["y", "topic_id"]).size() / yr.groupby("y").size()).unstack().fillna(0)
trend.to_csv(OUT / "topic_trend_year.csv"); T["trend_year"] = trend.round(4).to_dict("index")
order = tp.sort_values("share").index
fig, ax = plt.subplots(figsize=(6.6, 0.32 * K + 0.9))
ax.barh(tp.loc[order, "name"], tp.loc[order, "share"] * 100, color=V.RED, height=0.6)
for yv, (s, n) in enumerate(zip(tp.loc[order, "share"], tp.loc[order, "n_reviews"])):
    ax.text(s * 100, yv, f" {s:.1%} ({V.thousands(n)})".replace("%", " %").replace(".", ",", 1), va="center", fontsize=7.5, color=V.INK2)
ax.set_xlabel("Tỷ trọng trong đánh giá tiêu cực (%)"); ax.grid(axis="y", visible=False); ax.set_xlim(0, tp.share.max() * 100 * 1.35)
ax.set_title(f"Chủ đề phàn nàn (NMF, k = {K}, n = {V.thousands(len(neg))} đánh giá 1–2 sao)")
V.save(fig, FIG / "topic_02_share.png")

# %%
(OUT / "topic_results.json").write_text(json.dumps(T, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(json.dumps({k: T[k] for k in ["n_docs", "k_chosen", "lda_compare", "no_topic"]}, ensure_ascii=False))
