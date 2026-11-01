"""EdaService – KPI và dữ liệu biểu đồ khám phá (FR-07, FR-08, FR-09). Thiết kế theo notebook 01_eda."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from backend.core import config as C
from backend.services.data_service import model_preprocess

KW_STOP = sorted(ENGLISH_STOP_WORDS - {"not", "no", "nor", "never", "too", "very"}
                 | {"br", "amazon", "product", "products", "just", "like", "really", "got", "did", "does", "thought"})


def apply_filters(df: pd.DataFrame, f: dict | None) -> pd.DataFrame:
    """Lọc đồng thời (AND) theo tháng, mã sản phẩm, cảm xúc, số sao (FR-09)."""
    if not f:
        return df
    m = np.ones(len(df), dtype=bool)
    if f.get("date_from"):
        m &= (df.year_month >= f["date_from"]).values
    if f.get("date_to"):
        m &= (df.year_month <= f["date_to"]).values
    if f.get("product_id"):
        m &= (df.product_id == f["product_id"].strip().upper()).values
    if f.get("sentiment"):
        m &= (df.sentiment == f["sentiment"]).values
    if f.get("score"):
        m &= (df.score == int(f["score"])).values
    return df[m]


def log_odds_keywords(docs: pd.Series, sent: pd.Series, top: int = 15, min_df: int = 20) -> dict:
    """Từ/cụm từ đặc trưng nhóm Tiêu cực vs Tích cực: log-odds có prior Dirichlet (Monroe và cộng sự, 2008)."""
    mask = sent.isin(["neg", "pos"]).values
    docs, sent = docs[mask], sent[mask]
    if (sent == "neg").sum() < 20 or (sent == "pos").sum() < 20:
        return {"neg": {}, "pos": {}}
    cv = CountVectorizer(preprocessor=model_preprocess, stop_words=KW_STOP, ngram_range=(1, 2),
                         min_df=max(3, min(min_df, len(docs) // 2000)), max_features=40_000)
    X = cv.fit_transform(docs.values)
    vocab = np.array(cv.get_feature_names_out())
    neg = np.asarray(X[(sent == "neg").values].sum(0)).ravel(); pos = np.asarray(X[(sent == "pos").values].sum(0)).ravel()
    a = (neg + pos) / max((neg + pos).sum(), 1) * 1000
    ni, nj, a0 = neg.sum(), pos.sum(), a.sum()
    d = np.log((neg + a) / (ni + a0 - neg - a)) - np.log((pos + a) / (nj + a0 - pos - a))
    z = d / np.sqrt(1 / (neg + a) + 1 / (pos + a))
    o = np.argsort(z)
    return {"neg": {vocab[i]: round(float(z[i]), 1) for i in o[::-1][:top]},
            "pos": {vocab[i]: round(float(-z[i]), 1) for i in o[:top]}}


def group_stats(d: pd.DataFrame, key: str) -> pd.DataFrame:
    """n, avg_score, neg_rate theo khóa – tính vector hóa (nhanh với 67 nghìn sản phẩm)."""
    g = d.score.groupby(d[key])
    out = pd.DataFrame({"n": g.size(), "avg_score": g.mean(), "neg_rate": d.sentiment.eq("neg").groupby(d[key]).mean()})
    return out.reset_index()


def precompute(df: pd.DataFrame) -> dict:
    smp = df.sample(min(150_000, len(df)), random_state=C.RANDOM_STATE)
    kw = log_odds_keywords(smp.summary + " . " + smp.text, smp.sentiment)
    return {"keywords": kw}


def kpi(state, f: dict | None) -> dict:
    d = apply_filters(state.df, f)
    n = len(d)
    avg = float(d.score.mean()) if n else 0.0
    n_high = None
    if state.products is not None:
        p = state.products
        if f and f.get("product_id"):
            p = p[p.product_id == f["product_id"].strip().upper()]
        n_high = int((p.risk_level == "high").sum())
    return {"meta": state.meta_block(f), "n_reviews": n, "n_products": int(d.product_id.nunique()),
            "n_users": int(d.user_key.nunique()), "avg_score": round(avg, 4),
            "neg_rate": round(float((d.sentiment == "neg").mean()) if n else 0.0, 4),
            "model_f1_macro": state.registry["selected_metrics"]["f1_macro3"] if state.registry else None,
            "n_high_risk_products": n_high, "satisfaction_index": round(C.satisfaction_index(avg), 2) if n else 0.0}


def chart(state, name: str, f: dict | None) -> dict:
    d = apply_filters(state.df, f)
    if name == "score_dist":
        vc = d.score.value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
        data = [{"score": int(k), "n": int(v), "share": round(v / max(len(d), 1), 4),
                 "sentiment": "neg" if k <= 2 else ("neu" if k == 3 else "pos")} for k, v in vc.items()]
    elif name == "monthly":
        g = group_stats(d, "year_month")
        data = [{"month": r.year_month, "n": int(r.n), "avg_score": round(r.avg_score, 4), "neg_rate": round(r.neg_rate, 4),
                 "sat_index": round(C.satisfaction_index(r.avg_score), 2)} for r in g.itertuples()]
    elif name == "length_by_score":
        q = d.groupby("score").n_words.describe(percentiles=[.25, .5, .75])
        data = [{"score": int(s), "q1": float(r["25%"]), "median": float(r["50%"]), "q3": float(r["75%"]),
                 "mean": round(float(r["mean"]), 1), "n": int(r["count"])} for s, r in q.iterrows()]
    elif name == "keywords":
        if not f or not any(f.values()):
            kw = state.eda.get("keywords", {"neg": {}, "pos": {}})
        else:
            smp = d.sample(min(20_000, len(d)), random_state=C.RANDOM_STATE)
            kw = log_odds_keywords(smp.summary + " . " + smp.text, smp.sentiment, min_df=5)
        data = [{"sentiment": "neg", "term": k, "z": v} for k, v in kw.get("neg", {}).items()] + \
               [{"sentiment": "pos", "term": k, "z": v} for k, v in kw.get("pos", {}).items()]
    elif name == "top_products":
        g = group_stats(d, "product_id").sort_values("n", ascending=False).head(10)
        data = [{"product_id": r.product_id, "n": int(r.n), "avg_score": round(r.avg_score, 3), "neg_rate": round(r.neg_rate, 4)} for r in g.itertuples()]
    else:
        raise KeyError(name)
    return {"meta": state.meta_block(f), "chart": name, "data": data}
