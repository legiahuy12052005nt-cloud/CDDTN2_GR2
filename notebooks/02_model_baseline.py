# %% [markdown]
# # 02 – Thiết kế thực nghiệm và baseline mô hình dự đoán số sao / cảm xúc
# Buổi 5 – Thiết kế chi tiết. Người thực hiện chính: KAYSONE Souk Anong.
# Thiết kế: tách 70/10/20 (train/validation/test) phân tầng theo số sao sau khi bỏ trùng;
# chọn siêu tham số trên validation; huấn luyện lại trên 80% (train+validation) và đánh giá MỘT lần trên test 20%.

# %%
import sys, time, json
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
import matplotlib as mpl
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import f1_score, accuracy_score, precision_recall_fscore_support, confusion_matrix
from backend.core import config as C
from backend.services import data_service as DS
import vizstyle as V
V.apply()
FIG = ROOT / "notebooks" / "figures"; OUT = ROOT / "notebooks" / "outputs"
R = {}

# %%
df = pd.read_csv(C.DATA_PROCESSED / "reviews_clean.csv", usecols=["review_id", "score", "year_month", "summary", "text"],
                 dtype={"summary": str, "text": str}, keep_default_na=False)
df["doc"] = df.summary + " . " + df.text          # FR-10: dùng cả tiêu đề và nội dung
y = df.score.values
idx = np.arange(len(df))
i_trval, i_test = train_test_split(idx, test_size=C.TEST_SIZE, stratify=y, random_state=C.RANDOM_STATE)
i_train, i_val = train_test_split(i_trval, test_size=C.VAL_SIZE_OF_TRAIN, stratify=y[i_trval], random_state=C.RANDOM_STATE)
R["split"] = {"n_total": len(df), "train": len(i_train), "val": len(i_val), "test": len(i_test),
              "test_score_dist": {int(k): int(v) for k, v in pd.Series(y[i_test]).value_counts().sort_index().items()}}
R["split"]

# %% [markdown]
# ## Hàm đánh giá dùng chung (thước đo theo NFR-03)

# %%
SENT = np.array([0, 0, 0, 1, 2, 2])          # chỉ số theo số sao: 1–2 → 0 (Tiêu cực), 3 → 1, 4–5 → 2
def sent_from_proba(P):                     # P: n × 5 (1..5 sao) → cảm xúc theo tổng xác suất
    return np.argmax(np.c_[P[:, 0] + P[:, 1], P[:, 2], P[:, 3] + P[:, 4]], axis=1)

def evaluate(y_true, P=None, y_pred=None):
    if P is not None: y_pred = P.argmax(1) + 1
    s_true = SENT[y_true]; s_pred = sent_from_proba(P) if P is not None else SENT[y_pred]
    p, r, f, _ = precision_recall_fscore_support(s_true, s_pred, labels=[0, 1, 2], zero_division=0)
    out = {"f1_macro3": f1_score(s_true, s_pred, average="macro"), "f1_neg": f[0], "f1_neu": f[1], "f1_pos": f[2],
           "prec_neg": p[0], "rec_neg": r[0], "prec_neu": p[1], "rec_neu": r[1], "prec_pos": p[2], "rec_pos": r[2],
           "acc3": accuracy_score(s_true, s_pred), "acc5": accuracy_score(y_true, y_pred),
           "f1_macro5": f1_score(y_true, y_pred, average="macro"), "mae": float(np.abs(y_true - y_pred).mean())}
    if P is not None: out["mae_expected"] = float(np.abs(y_true - (P * np.arange(1, 6)).sum(1)).mean())
    return {k: round(float(v), 4) for k, v in out.items()}

def make_vec(): return TfidfVectorizer(preprocessor=DS.model_preprocess, ngram_range=C.TFIDF_NGRAM, min_df=C.TFIDF_MIN_DF,
                                       max_features=C.TFIDF_MAX_FEATURES, sublinear_tf=True, dtype=np.float32)

# %% [markdown]
# ## B0 – Baseline đơn giản nhất: luôn dự đoán lớp đông nhất (5 sao)

# %%
R["B0_majority"] = evaluate(y[i_test], y_pred=np.full(len(i_test), 5)); R["B0_majority"]

# %% [markdown]
# ## Chọn siêu tham số trên tập validation

# %%
# Chọn siêu tham số trên mẫu phân tầng 100.000 dòng của tập train (đúng quy mô huấn luyện của ứng dụng),
# đánh giá trên toàn bộ tập validation.
i_tune = train_test_split(i_train, train_size=C.TRAIN_SAMPLE_MAX, stratify=y[i_train], random_state=C.RANDOM_STATE)[0]
t0 = time.time(); vec = make_vec(); Xtr = vec.fit_transform(df.doc.values[i_tune]); Xva = vec.transform(df.doc.values[i_val])
R["tfidf_fit_seconds_100k"] = round(time.time() - t0, 1); R["vocab_size_100k"] = len(vec.vocabulary_)
ytr, yva = y[i_tune], y[i_val]; sw = compute_sample_weight("balanced", ytr)
grid = {"LR": [0.5, 1.0, 2.0, 4.0], "NB": [0.03, 0.1, 0.3, 1.0], "SVM": [0.05, 0.1, 0.3]}
tune = []
for c in grid["LR"]:
    t0 = time.time(); m = LogisticRegression(C=c, class_weight="balanced", max_iter=300, solver="lbfgs").fit(Xtr, ytr)
    tune.append({"model": "LR", "param": f"C={c}", "sec": round(time.time() - t0, 1), **evaluate(yva, P=m.predict_proba(Xva))}); print(tune[-1]["model"], tune[-1]["param"], tune[-1]["f1_macro3"], flush=True)
for a in grid["NB"]:
    t0 = time.time(); m = MultinomialNB(alpha=a).fit(Xtr, ytr, sample_weight=sw)
    tune.append({"model": "NB", "param": f"alpha={a}", "sec": round(time.time() - t0, 1), **evaluate(yva, P=m.predict_proba(Xva))})
for c in grid["SVM"]:
    t0 = time.time(); m = CalibratedClassifierCV(LinearSVC(C=c, class_weight="balanced"), cv=3, method="sigmoid").fit(Xtr, ytr)
    tune.append({"model": "SVM", "param": f"C={c}", "sec": round(time.time() - t0, 1), **evaluate(yva, P=m.predict_proba(Xva))})
tune = pd.DataFrame(tune); tune.to_csv(OUT / "model_tuning_val.csv", index=False)
best = tune.loc[tune.groupby("model").f1_macro3.idxmax()].set_index("model")
R["tuning_best"] = best[["param", "f1_macro3", "f1_neg", "mae"]].to_dict("index")
tune[["model", "param", "sec", "f1_macro3", "f1_neg", "f1_neu", "mae", "acc5"]]

# %% [markdown]
# ## Đường học (learning curve) – căn cứ cho quyết định lấy mẫu 100.000 dòng khi file lớn

# %%
lc = []
bestC = float(best.loc["LR", "param"].split("=")[1])
for n in [25_000, 50_000, 100_000, 200_000]:
    sub = i_train if n == len(i_train) else train_test_split(i_train, train_size=n, stratify=y[i_train], random_state=C.RANDOM_STATE)[0]
    t0 = time.time(); v = make_vec(); Xs = v.fit_transform(df.doc.values[sub])
    m = LogisticRegression(C=bestC, class_weight="balanced", max_iter=300).fit(Xs, y[sub]); sec = time.time() - t0
    lc.append({"n_train": n, "sec_fit_total": round(sec, 1), **evaluate(yva, P=m.predict_proba(v.transform(df.doc.values[i_val])))}); print("LC", n, lc[-1]["f1_macro3"], flush=True)
lc = pd.DataFrame(lc); lc.to_csv(OUT / "learning_curve.csv", index=False); R["learning_curve"] = lc.to_dict("records")
lc[["n_train", "sec_fit_total", "f1_macro3", "f1_neg", "mae"]]

# %% [markdown]
# ## Huấn luyện lại cấu hình tốt nhất trên 80% và đánh giá một lần trên test 20%

# %%
t0 = time.time(); vecF = make_vec(); Xtv = vecF.fit_transform(df.doc.values[i_trval]); Xte = vecF.transform(df.doc.values[i_test])
ytv, yte = y[i_trval], y[i_test]; swF = compute_sample_weight("balanced", ytv)
R["tfidf_fit_seconds_80"] = round(time.time() - t0, 1)
final = {}
for name in ["LR", "NB", "SVM"]:
    prm = float(best.loc[name, "param"].split("=")[1]); t0 = time.time()
    if name == "LR": m = LogisticRegression(C=prm, class_weight="balanced", max_iter=300).fit(Xtv, ytv)
    elif name == "NB": m = MultinomialNB(alpha=prm).fit(Xtv, ytv, sample_weight=swF)
    else: m = CalibratedClassifierCV(LinearSVC(C=prm, class_weight="balanced"), cv=3, method="sigmoid").fit(Xtv, ytv)
    sec = round(time.time() - t0, 1); P = m.predict_proba(Xte)
    final[name] = {"model": m, "P": P, "res": {"param": best.loc[name, "param"], "fit_seconds": sec, **evaluate(yte, P=P)}}; print("FINAL", name, final[name]["res"]["f1_macro3"], flush=True)
R["test"] = {k: v["res"] for k, v in final.items()}
pd.DataFrame(R["test"]).T

# %% [markdown]
# ## Chế độ của ứng dụng: huấn luyện trên mẫu phân tầng 100.000 dòng, đánh giá trên cùng tập test

# %%
sub = train_test_split(i_trval, train_size=C.TRAIN_SAMPLE_MAX, stratify=y[i_trval], random_state=C.RANDOM_STATE)[0]
t0 = time.time(); v100 = make_vec(); X100 = v100.fit_transform(df.doc.values[sub])
m100 = LogisticRegression(C=bestC, class_weight="balanced", max_iter=300).fit(X100, y[sub]); sec = time.time() - t0
R["app_mode_100k"] = {"fit_seconds_total": round(sec, 1), **evaluate(yte, P=m100.predict_proba(v100.transform(df.doc.values[i_test])))}
R["app_mode_100k"]

# %% [markdown]
# ## Đối chứng thiết kế QĐ-03: mô hình 3 lớp trực tiếp so với mô hình 5 sao suy ra 3 lớp (cùng mẫu 100.000 dòng)

# %%
m3 = LogisticRegression(C=bestC, class_weight="balanced", max_iter=300).fit(X100, SENT[y[sub]])
s_pred = m3.predict(v100.transform(df.doc.values[i_test]))
R["ablation_direct3_100k"] = {"f1_macro3": round(f1_score(SENT[yte], s_pred, average="macro"), 4),
                              "f1_neg": round(f1_score(SENT[yte], s_pred, labels=[0], average="macro"), 4),
                              "compare_5to3_100k": {k: R["app_mode_100k"][k] for k in ["f1_macro3", "f1_neg"]}}
R["ablation_direct3_100k"]

# %% [markdown]
# ## Kiểm tra trôi dữ liệu theo thời gian: huấn luyện trước 2012, kiểm tra trên dữ liệu năm 2012

# %%
old = np.where(df.year_month.values < "2012-01")[0]; new = np.where(df.year_month.values >= "2012-01")[0]
sub_old = train_test_split(old, train_size=C.TRAIN_SAMPLE_MAX, stratify=y[old], random_state=C.RANDOM_STATE)[0]
v_o = make_vec(); m_o = LogisticRegression(C=bestC, class_weight="balanced", max_iter=300).fit(v_o.fit_transform(df.doc.values[sub_old]), y[sub_old])
R["out_of_time_2012"] = {"n_test": len(new), **evaluate(y[new], P=m_o.predict_proba(v_o.transform(df.doc.values[new])))}
R["out_of_time_2012"]

# %% [markdown]
# ## Ma trận nhầm lẫn, độ trễ dự đoán, đánh giá lệch, từ khóa ảnh hưởng (mô hình được chọn)

# %%
sel = max(R["tuning_best"], key=lambda k: R["tuning_best"][k]["f1_macro3"]); R["selected"] = sel   # chọn trên validation; test chỉ để báo cáo
Psel = final[sel]["P"]; msel = final[sel]["model"]
cm3 = confusion_matrix(SENT[yte], sent_from_proba(Psel), labels=[0, 1, 2]); cm5 = confusion_matrix(yte, Psel.argmax(1) + 1, labels=[1, 2, 3, 4, 5])
R["confusion3"] = cm3.tolist(); R["confusion5"] = cm5.tolist()
# độ trễ: vector hóa + dự đoán 1 đánh giá, lặp 200 lần
docs = df.doc.values[i_test[:200]]; t0 = time.perf_counter()
for d in docs: msel.predict_proba(vecF.transform([d]))
R["latency_ms_per_review"] = round((time.perf_counter() - t0) / len(docs) * 1000, 2)
# đánh giá lệch (FR-13): 5 sao nhưng P(Tiêu cực) >= 0,8 và ngược lại
pneg = Psel[:, 0] + Psel[:, 1]; ppos = Psel[:, 3] + Psel[:, 4]
R["mismatch_test"] = {"5star_but_neg": int(((yte == 5) & (pneg >= C.MISMATCH_PROB)).sum()),
                      "1star_but_pos": int(((yte == 1) & (ppos >= C.MISMATCH_PROB)).sum())}
ex = df.iloc[i_test[(yte == 5) & (pneg >= C.MISMATCH_PROB)][:3]][["review_id", "score", "summary"]]
R["mismatch_examples"] = ex.to_dict("records")
# từ khóa ảnh hưởng: w_j = Σ_k (k − 3)·β_kj trên mô hình LR
lr = final["LR"]["model"]; w = ((np.arange(1, 6) - 3)[:, None] * lr.coef_).sum(0)
vocab = np.array(vecF.get_feature_names_out()); o = np.argsort(w)
R["keywords_up"] = dict(zip(vocab[o[::-1][:15]], np.round(w[o[::-1][:15]], 2).tolist()))
R["keywords_down"] = dict(zip(vocab[o[:15]], np.round(w[o[:15]], 2).tolist()))
R["latency_ms_per_review"], R["mismatch_test"], R["keywords_down"]

# %%
fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.8), gridspec_kw={"wspace": 0.45})
names = ["B0", "NB", "SVM", "LR"]; lab = ["Luôn 5 sao", "Naive Bayes", "Linear SVM", "Logistic Reg."]
vals = [R["B0_majority"]] + [R["test"][k] for k in ["NB", "SVM", "LR"]]
comma = mpl.ticker.FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))
for ax, key, title, thr, better in [(axs[0], "f1_macro3", "a) F1-macro 3 lớp ↑", 0.65, "≥"), (axs[1], "f1_neg", "b) F1 lớp Tiêu cực ↑", 0.75, "≥"), (axs[2], "mae", "c) MAE số sao ↓", 0.8, "≤")]:
    v = [d[key] for d in vals]; colors = [V.GRAY, V.BLUE, V.BLUE, V.BLUE]
    bars = ax.barh(lab, v, color=colors, height=0.6); ax.axvline(thr, color=V.ORANGE, lw=1.2, ls="--")
    ax.set_title(title, pad=8); ax.grid(axis="y", visible=False); ax.set_ylim(-1.15, 3.5)
    ax.text(thr, -0.95, f" NFR-03 {better} {thr}".replace(".", ","), fontsize=7, color=V.ORANGE, ha="left", va="center")   # nhãn ngưỡng đặt dưới, không đè tiêu đề
    for b, x in zip(bars, v): ax.text(x, b.get_y() + b.get_height() / 2, f" {x:.3f}".replace(".", ","), va="center", fontsize=7, color=V.INK2)
    if ax is not axs[0]: ax.set_yticklabels([])
    ax.set_xlim(0, max(max(v), thr) * 1.32); ax.xaxis.set_major_formatter(comma)
V.save(fig, FIG / "model_01_compare.png")

fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"wspace": 0.4})
for ax, cm, labs, title in [(axs[0], cm3, ["Tiêu cực", "Trung tính", "Tích cực"], "a) 3 lớp cảm xúc"), (axs[1], cm5, ["1", "2", "3", "4", "5"], "b) 5 mức sao")]:
    cmn = cm / cm.sum(1, keepdims=True)
    ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{cmn[i, j]:.0%}", ha="center", va="center", fontsize=7.5, color="white" if cmn[i, j] > 0.55 else V.INK)
    ax.set_xticks(range(len(labs)), labs, fontsize=7.5); ax.set_yticks(range(len(labs)), labs, fontsize=7.5)
    ax.set_xlabel("Dự đoán"); ax.set_ylabel("Thực tế"); ax.set_title(title); ax.grid(False)
V.save(fig, FIG / "model_02_confusion.png")

fig, ax = plt.subplots(figsize=(6.4, 2.6))
ax.plot(lc.n_train / 1000, lc.f1_macro3, marker="o", color=V.BLUE, label="F1-macro 3 lớp")
ax.plot(lc.n_train / 1000, lc.f1_neg, marker="o", color=V.RED, label="F1 lớp Tiêu cực")
ax.axvline(100, color=V.ORANGE, ls="--", lw=1.2); ax.text(102, lc.f1_macro3.min(), "mẫu 100.000 dòng\n(chế độ ứng dụng)", fontsize=7, color=V.ORANGE)
ax.set_xlabel("Số đánh giá dùng để huấn luyện (nghìn)"); ax.set_title("Đường học của TF-IDF + Logistic Regression (đo trên validation)"); ax.legend(loc="lower right")
V.save(fig, FIG / "model_03_learning_curve.png")

# %%
import joblib
joblib.dump(vecF, C.MODELS_DIR / "vectorizer.joblib", compress=3); joblib.dump(final[sel]["model"], C.MODELS_DIR / "star_model.joblib", compress=3)
(OUT / "model_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(json.dumps({k: R[k] for k in ["test", "selected", "app_mode_100k", "out_of_time_2012", "ablation_direct3_100k", "latency_ms_per_review"]}, ensure_ascii=False, indent=1, default=float))
