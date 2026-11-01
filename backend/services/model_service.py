"""ModelService – huấn luyện, so sánh, dự đoán, giải thích (FR-10 – FR-15). Thiết kế theo notebook 02.

- Dữ liệu: bảng REVIEW đã làm sạch (R1–R9). File > 100.000 dòng → mẫu phân tầng 100.000 dòng để huấn luyện.
- Chia 80/20 phân tầng theo số sao (FR-11), random_state = 42.
- 3 mô hình với siêu tham số đã chọn ở buổi 5: LR (C=4), Multinomial NB (alpha=0,3), Linear SVM (C=0,3, hiệu chỉnh xác suất).
- Mô hình dùng để dự đoán là cấu hình đã chọn trên tập validation ở thực nghiệm E-C1 (C.SELECTED_MODEL = LR).
  Tập kiểm tra 20% chỉ dùng để báo cáo bảng so sánh (FR-11), không dùng để chọn lại mô hình; nhờ vậy phần
  giải thích từ khóa (hệ số LR – FR-12, FR-15) luôn khớp với mô hình đang dự đoán.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.utils.class_weight import compute_sample_weight

from backend.core import config as C
from backend.services.data_service import model_preprocess

SENT = np.array([0, 0, 0, 1, 2, 2])            # theo số sao 1..5
SENT_CODE = np.array(["neg", "neu", "pos"])


def make_vectorizer(n_docs: int) -> TfidfVectorizer:
    return TfidfVectorizer(preprocessor=model_preprocess, ngram_range=C.TFIDF_NGRAM,
                           min_df=C.TFIDF_MIN_DF if n_docs > 5000 else 1,
                           max_features=C.TFIDF_MAX_FEATURES, sublinear_tf=True, dtype=np.float32)


def sent_from_proba(P: np.ndarray) -> np.ndarray:
    return np.argmax(np.c_[P[:, 0] + P[:, 1], P[:, 2], P[:, 3] + P[:, 4]], axis=1)


def evaluate(y_true, P=None, y_pred=None) -> dict:
    if P is not None:
        y_pred = P.argmax(1) + 1
    s_true = SENT[y_true]; s_pred = sent_from_proba(P) if P is not None else SENT[y_pred]
    p, r, f, _ = precision_recall_fscore_support(s_true, s_pred, labels=[0, 1, 2], zero_division=0)
    out = {"f1_macro3": f1_score(s_true, s_pred, average="macro", labels=[0, 1, 2], zero_division=0),
           "f1_neg": f[0], "f1_neu": f[1], "f1_pos": f[2], "prec_neg": p[0], "rec_neg": r[0],
           "acc3": accuracy_score(s_true, s_pred), "acc5": accuracy_score(y_true, y_pred),
           "mae": float(np.abs(y_true - y_pred).mean())}
    return {k: round(float(v), 4) for k, v in out.items()}


def _full_proba(model, X) -> np.ndarray:
    """Xác suất đủ 5 cột 1..5 kể cả khi tập huấn luyện thiếu lớp."""
    P = model.predict_proba(X)
    if P.shape[1] == 5:
        return P
    out = np.zeros((X.shape[0], 5)); out[:, np.asarray(model.classes_) - 1] = P
    return out


def train(df: pd.DataFrame, progress=lambda pct, msg: None) -> tuple[dict, dict, pd.DataFrame]:
    """Trả về (bundle lưu joblib, registry JSON, bảng predictions của tập test)."""
    d = df[["review_id", "score", "summary", "text"]]
    n_all = len(d)
    if n_all > C.TRAIN_SAMPLE_MAX:
        d, _ = train_test_split(d, train_size=C.TRAIN_SAMPLE_MAX, stratify=d.score, random_state=C.RANDOM_STATE)
    docs = (d.summary + " . " + d.text).values; y = d.score.values.astype(int)
    strat = y if pd.Series(y).value_counts().min() >= 2 else None
    i_tr, i_te = train_test_split(np.arange(len(d)), test_size=C.TEST_SIZE, stratify=strat, random_state=C.RANDOM_STATE)
    t0 = time.time(); progress(5, "Vector hóa TF-IDF")
    vec = make_vectorizer(len(d)); Xtr = vec.fit_transform(docs[i_tr]); Xte = vec.transform(docs[i_te])
    ytr, yte = y[i_tr], y[i_te]
    t_vec = time.time() - t0
    results, models = [], {}
    b0 = evaluate(yte, y_pred=np.full(len(yte), 5))
    results.append({"model": "B0", "params": "luôn 5 sao", "fit_seconds": 0.0, **b0})
    progress(20, "Huấn luyện Naive Bayes")
    t0 = time.time(); nb = MultinomialNB(alpha=C.NB_ALPHA).fit(Xtr, ytr, sample_weight=compute_sample_weight("balanced", ytr))
    models["NB"] = nb; results.append({"model": "NB", "params": f"alpha={C.NB_ALPHA}", "fit_seconds": round(time.time() - t0, 1), **evaluate(yte, P=_full_proba(nb, Xte))})
    progress(30, "Huấn luyện Linear SVM")
    t0 = time.time()
    cv = 3 if pd.Series(ytr).value_counts().min() >= 3 else 2
    svm = CalibratedClassifierCV(LinearSVC(C=C.SVM_C, class_weight="balanced"), cv=cv, method="sigmoid").fit(Xtr, ytr)
    models["SVM"] = svm; results.append({"model": "SVM", "params": f"C={C.SVM_C}", "fit_seconds": round(time.time() - t0, 1), **evaluate(yte, P=_full_proba(svm, Xte))})
    progress(50, "Huấn luyện Logistic Regression")
    t0 = time.time(); lr = LogisticRegression(C=C.LR_C, class_weight="balanced", max_iter=300).fit(Xtr, ytr)
    models["LR"] = lr; results.append({"model": "LR", "params": f"C={C.LR_C}", "fit_seconds": round(time.time() - t0, 1), **evaluate(yte, P=_full_proba(lr, Xte))})
    progress(85, "Đánh giá và lưu mô hình")
    sel = C.SELECTED_MODEL                      # chọn trên validation ở E-C1, không chọn lại trên tập kiểm tra
    best_test = max((r for r in results if r["model"] != "B0"), key=lambda r: r["f1_macro3"])["model"]
    for r in results:
        r["selected"] = r["model"] == sel
    Psel = _full_proba(models[sel], Xte)
    cm3 = confusion_matrix(SENT[yte], sent_from_proba(Psel), labels=[0, 1, 2]).tolist()
    cm5 = confusion_matrix(yte, Psel.argmax(1) + 1, labels=[1, 2, 3, 4, 5]).tolist()
    # trọng số giải thích: w_j = Σ_k (k − 3)·β_kj (hệ số LR, đủ 5 lớp)
    coef = np.zeros((5, lr.coef_.shape[1])); coef[np.asarray(lr.classes_) - 1] = lr.coef_
    w = ((np.arange(1, 6) - 3)[:, None] * coef).sum(0)
    vocab = np.array(vec.get_feature_names_out()); o = np.argsort(w)
    keywords = {"up": [{"term": vocab[i], "weight": round(float(w[i]), 2)} for i in o[::-1][:50]],
                "down": [{"term": vocab[i], "weight": round(float(w[i]), 2)} for i in o[:50]]}
    # predictions của tập test (bảng PREDICTION)
    pneg = Psel[:, 0] + Psel[:, 1]; ppos = Psel[:, 3] + Psel[:, 4]
    pred = pd.DataFrame({"review_id": d.review_id.values[i_te], "split": "test", "score": yte, "pred_star": Psel.argmax(1) + 1,
                         **{f"p{k}": np.round(Psel[:, k - 1], 4) for k in range(1, 6)},
                         "pred_sentiment": SENT_CODE[sent_from_proba(Psel)],
                         "sat_index_pred": np.round(((Psel * np.arange(1, 6)).sum(1) - 1) / 4 * 100, 2),
                         "p_neg": np.round(pneg, 4), "p_pos": np.round(ppos, 4)})
    pred["is_mismatch"] = ((pred.score == 5) & (pred.p_neg >= C.MISMATCH_PROB)) | ((pred.score == 1) & (pred.p_pos >= C.MISMATCH_PROB))
    registry = {"model_id": f"{sel}-{int(time.time())}", "selected": sel, "trained_at": pd.Timestamp.now().isoformat(timespec="seconds"),
                "split": {"n_dataset": n_all, "n_used": len(d), "train": len(i_tr), "test": len(i_te), "stratify": "score",
                          "random_state": C.RANDOM_STATE, "sampled": n_all > C.TRAIN_SAMPLE_MAX},
                "vectorizer": {"ngram": list(C.TFIDF_NGRAM), "n_features": len(vocab), "fit_seconds": round(t_vec, 1)},
                "models": results, "selected_metrics": next(r for r in results if r["model"] == sel),
                "selection_rule": "LR – cấu hình chọn trên tập validation ở thực nghiệm E-C1; tập kiểm tra chỉ dùng để báo cáo",
                "best_on_test": best_test,
                "confusion3": cm3, "confusion5": cm5, "keywords": keywords,
                "n_mismatch": int(pred.is_mismatch.sum())}
    bundle = {"vectorizer": vec, "model": models[sel], "selected": sel, "lr": lr, "weights": w.astype(np.float32), "vocab": vocab}
    return bundle, registry, pred


def time_check(df: pd.DataFrame, random_metrics: dict | None = None, progress=lambda pct, msg: None) -> dict | None:
    """Kiểm tra theo thời gian (notebook 02, “trôi dữ liệu”): LR cùng cấu hình học trên đánh giá TRƯỚC năm cuối của dữ liệu,
    kiểm tra trên đánh giá CỦA năm cuối. Trả lời câu hỏi: chia ngẫu nhiên có làm kết quả đẹp hơn thực tế không
    (đánh giá gần giống nhau, cùng sản phẩm rơi vào cả hai tập), và mô hình còn đúng khi dùng cho dữ liệu mới hơn không.

    Năm cuối quá ít dữ liệu (file nhỏ): lấy 20% đánh giá mới nhất làm tập kiểm tra.
    """
    d = df[["review_date", "score", "summary", "text"]]
    year = d.review_date.str[:4]
    last_year = year.max()
    cut = f"{last_year}-01-01"
    is_new = (d.review_date >= cut).values
    if is_new.sum() < C.TIME_CHECK_MIN_TEST or (~is_new).sum() < C.TIME_CHECK_MIN_TRAIN:
        cut = str(d.review_date.sort_values().iloc[int(len(d) * 0.8)])
        is_new = (d.review_date >= cut).values
    old, new = np.where(~is_new)[0], np.where(is_new)[0]
    if len(new) < C.TIME_CHECK_MIN_TEST or len(old) < C.TIME_CHECK_MIN_TRAIN:
        return None
    y = d.score.values.astype(int)
    rng = np.random.RandomState(C.RANDOM_STATE)
    if len(old) > C.TIME_CHECK_TRAIN_MAX:
        strat = y[old] if pd.Series(y[old]).value_counts().min() >= 2 else None
        old = train_test_split(old, train_size=C.TIME_CHECK_TRAIN_MAX, stratify=strat, random_state=C.RANDOM_STATE)[0]
    if len(new) > C.TIME_CHECK_TEST_MAX:
        new = rng.choice(new, C.TIME_CHECK_TEST_MAX, replace=False)
    docs = (d.summary + " . " + d.text).values
    progress(0, "Kiểm tra theo thời gian: vector hóa")
    vec = make_vectorizer(len(old)); Xtr = vec.fit_transform(docs[old]); Xte = vec.transform(docs[new])
    progress(40, "Kiểm tra theo thời gian: huấn luyện LR trên dữ liệu cũ")
    t0 = time.time()
    lr = LogisticRegression(C=C.LR_C, class_weight="balanced", max_iter=300).fit(Xtr, y[old])
    m = evaluate(y[new], P=_full_proba(lr, Xte))
    dates = d.review_date.values
    out = {"rule": f"học trên đánh giá trước {cut[:10]}, kiểm tra trên đánh giá từ {cut[:10]}",
           "train_from": str(dates[old].min()), "train_to": str(dates[old].max()),
           "test_from": str(dates[new].min()), "test_to": str(dates[new].max()),
           "n_train": int(len(old)), "n_test": int(len(new)), "fit_seconds": round(time.time() - t0, 1),
           **{k: m[k] for k in ("f1_macro3", "f1_neg", "f1_neu", "f1_pos", "acc3", "acc5", "mae")}}
    if random_metrics:
        out["random_f1_macro3"] = random_metrics["f1_macro3"]
        out["gap"] = round(random_metrics["f1_macro3"] - m["f1_macro3"], 4)
    return out


def predict(bundle: dict, text: str, summary: str | None = None, top_tokens: int = 14) -> dict:
    doc = (summary or "") + " . " + text
    X = bundle["vectorizer"].transform([doc])
    P = _full_proba(bundle["model"], X)[0]
    star = int(P.argmax() + 1)
    sp = {"neg": float(P[0] + P[1]), "neu": float(P[2]), "pos": float(P[3] + P[4])}
    sentiment = max(sp, key=sp.get)
    sat = ((P * np.arange(1, 6)).sum() - 1) / 4 * 100
    # đóng góp từng từ = tfidf × w (FR-15)
    row = X.tocoo()
    vocab = bundle.get("vocab")
    if vocab is None:
        vocab = bundle["vocab"] = bundle["vectorizer"].get_feature_names_out()
    contrib = [(vocab[j], float(v * bundle["weights"][j])) for j, v in zip(row.col, row.data)]
    contrib.sort(key=lambda t: -abs(t[1]))
    tokens = [{"token": t, "weight": round(c, 3)} for t, c in contrib[:top_tokens] if abs(c) > 1e-3]
    return {"pred_star": star, "proba": {str(k + 1): round(float(P[k]), 4) for k in range(5)}, "sentiment": sentiment,
            "sentiment_proba": {k: round(v, 4) for k, v in sp.items()}, "satisfaction_index": round(float(sat), 2), "tokens": tokens}
