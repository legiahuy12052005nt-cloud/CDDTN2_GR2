"""TopicService – chủ đề phàn nàn trên đánh giá 1–2 sao (FR-15, FR-16, FR-18). Thiết kế theo notebook 03.

TF-IDF (bỏ từ dừng tiếng Anh + từ dừng miền) + NMF k = 9. Tên chủ đề: so khớp từ khóa với 9 chủ đề đã
được nhóm đặt tên ở buổi 5; chủ đề mới không khớp mẫu nào được đặt tên tự động theo 3 từ khóa đầu.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from backend.core import config as C
from backend.services.data_service import model_preprocess

DOMAIN_STOP = {"br", "amazon", "product", "products", "item", "just", "like", "really", "would", "could", "one", "get", "got",
               "buy", "bought", "order", "ordered", "purchase", "purchased", "review", "reviews", "even", "also", "much", "think",
               "know", "way", "make", "made", "use", "used", "say", "said", "thing", "things", "time", "try", "tried", "good", "bad",
               "great", "better", "best", "disappointed", "disappointing", "terrible", "horrible", "awful", "worst", "not", "don",
               "didn", "doesn", "isn", "wasn", "ve", "ll", "re", "did", "does", "doing", "will", "going", "want", "wanted", "thought",
               "stars", "star", "recommend", "money", "waste", "never", "again", "back", "first", "well", "still", "since"}
STOP = sorted(set(ENGLISH_STOP_WORDS) | DOMAIN_STOP)

TEMPLATES = [
    ("taste", "Hương vị, mùi, kết cấu không ngon", {"taste", "flavor", "tastes", "tasted", "texture", "smell", "sauce", "sweet", "bland", "salty", "water", "stuff"}),
    ("coffee", "Cà phê nhạt/đắng, viên K-cup", {"coffee", "cup", "cups", "weak", "instant", "roast", "instant coffee", "cup coffee", "bitter", "pods", "keurig", "beans"}),
    ("stale", "Hàng cũ, hết hạn, bao bì hỏng khi nhận", {"box", "received", "stale", "date", "arrived", "package", "bag", "opened", "packaging", "expiration", "broken", "damaged"}),
    ("tea", "Trà: vị nhạt, túi lọc", {"tea", "green", "green tea", "teas", "bags", "tea bags", "black", "chai", "black tea"}),
    ("pet", "Thức ăn thú cưng: xuất xứ, làm thú bệnh", {"dog", "food", "dogs", "eat", "treats", "cat", "cats", "china", "dog food", "chicken", "sick", "treat"}),
    ("price", "Giá cao so với cửa hàng, phí giao hàng", {"price", "store", "grocery", "local", "grocery store", "expensive", "worth", "shipping", "pay", "cost", "99", "00"}),
    ("ingredients", "Thành phần: đường, siro ngô, không tự nhiên", {"sugar", "ingredients", "syrup", "corn", "corn syrup", "sweet", "high", "ingredient", "natural", "fructose", "list"}),
    ("chocolate", "Sô-cô-la, bánh quy, bơ đậu phộng", {"chocolate", "hot", "bars", "cookies", "hot chocolate", "bar", "dark", "butter", "peanut", "dark chocolate", "cocoa"}),
    ("gluten", "Sản phẩm không gluten, bột làm bánh", {"free", "gluten", "gluten free", "wheat", "flour", "bread", "mix", "sugar free", "celiac", "rice", "gf"}),
]
# Bảng quy tắc gợi ý hành động (FR-16) – bảng 5.29 của tài liệu thiết kế
SUGGESTIONS = {
    "taste": "Rà soát công thức/nhà cung cấp; lấy mẫu nếm thử theo lô; ghi rõ hương vị, độ ngọt, kết cấu trên trang sản phẩm",
    "stale": "Kiểm tra hạn sử dụng khi nhập kho (FIFO), quy cách đóng gói chống va đập và đơn vị vận chuyển; bổ sung chính sách đổi trả",
    "price": "So sánh giá với kênh bán lẻ; xem lại phí vận chuyển, gói combo hoặc đăng ký định kỳ",
    "ingredients": "Công bố đầy đủ thành phần; thông báo rõ khi đổi công thức; cân nhắc phiên bản ít đường",
    "pet": "Công bố nguồn gốc nguyên liệu, chứng nhận an toàn; theo dõi phản ánh thú cưng bị bệnh để thu hồi kịp thời",
    "coffee": "Chuyển cho bộ phận ngành hàng cà phê: kiểm tra độ đậm, độ rang, độ tương thích của viên K-cup",
    "tea": "Chuyển cho bộ phận ngành hàng trà: kiểm tra độ đậm, chất lượng túi lọc, mô tả hương vị",
    "chocolate": "Chuyển cho bộ phận ngành hàng bánh kẹo: kiểm tra độ tươi, bảo quản nhiệt độ khi vận chuyển",
    "gluten": "Kiểm tra lại nhãn “không gluten”, nguy cơ nhiễm chéo; ghi rõ chứng nhận",
}
DEFAULT_SUGGESTION = "Đọc các đánh giá mẫu của chủ đề, xác định khâu gây lỗi (sản phẩm, đóng gói, giao hàng) và theo dõi tỷ lệ phàn nàn hằng tháng"


def _name_topics(top_words: list[list[str]]) -> list[tuple[str, str]]:
    """Ghép tham lam chủ đề ↔ mẫu theo số từ khóa trùng (≥ 3 từ mới nhận tên mẫu)."""
    pairs = sorted(((len(set(tw) & kw), i, key, name) for i, tw in enumerate(top_words) for key, name, kw in TEMPLATES), reverse=True)
    out, used_t, used_k = [None] * len(top_words), set(), set()
    for ov, i, key, name in pairs:
        if ov >= 3 and i not in used_t and key not in used_k:
            out[i] = (key, name); used_t.add(i); used_k.add(key)
    for i, tw in enumerate(top_words):
        if out[i] is None:
            # mẫu đã được chủ đề khác dùng nhưng vẫn khớp ≥ 3 từ (thường gặp với file nhỏ): giữ tên và gợi ý của mẫu,
            # thêm 3 từ khóa đầu để phân biệt; không khớp mẫu nào thì đặt tên tự động theo 3 từ khóa đầu
            ov, key, name = max((len(set(tw) & kw), key, name) for key, name, kw in TEMPLATES)
            out[i] = (key, f"{name} – nhóm phụ: {', '.join(tw[:3])}") if ov >= 3 else (f"auto{i}", "Chủ đề: " + ", ".join(tw[:3]))
    return out


def fit(df: pd.DataFrame, progress=lambda pct, msg: None, last_full: str | None = None):
    neg = df[df.sentiment == "neg"]
    if len(neg) < 50:
        return None, [], pd.DataFrame(columns=["review_id", "topic_id", "topic_weight"])
    k = int(min(C.TOPIC_K, max(2, len(neg) // 150)))
    docs = (neg.summary + " . " + neg.text).values
    progress(10, "Vector hóa đánh giá tiêu cực")
    vec = TfidfVectorizer(preprocessor=model_preprocess, stop_words=STOP, ngram_range=(1, 2),
                          min_df=int(min(10, max(2, len(neg) // 2000))), max_df=0.4, max_features=20_000, sublinear_tf=True)
    X = vec.fit_transform(docs)
    progress(50, f"NMF k = {k}")
    nmf = NMF(n_components=k, init="nndsvda", random_state=C.RANDOM_STATE, max_iter=400).fit(X)
    W = nmf.transform(X); vocab = np.array(vec.get_feature_names_out())
    top_words = [vocab[np.argsort(h)[::-1][:10]].tolist() for h in nmf.components_]
    names = _name_topics(top_words)
    tid = np.where(W.max(1) > 0, W.argmax(1), -1)
    rt = pd.DataFrame({"review_id": neg.review_id.values, "topic_id": tid, "topic_weight": np.round(W.max(1), 5)})
    nw = neg.n_words.values; ym = neg.year_month.values
    months_ok = pd.Series(ym).value_counts()
    months_ok = months_ok[months_ok >= 20]
    if last_full:                                   # bỏ tháng chưa trọn cuối dữ liệu (cùng mốc as_of của cảnh báo, dự báo)
        months_ok = months_ok[months_ok.index <= last_full]
    months_ok = sorted(months_ok.index)[-36:]
    topics = []
    for i in range(k):
        m = tid == i
        idx = np.where(m & (nw >= 25) & (nw <= 120))[0]
        if len(idx) < 3:
            idx = np.where(m)[0]
        idx = idx[np.argsort(-W[idx, i])][:3]
        sub = pd.DataFrame({"ym": ym, "t": tid})
        sub = sub[sub.ym.isin(months_ok)]
        tr = (sub.assign(hit=(sub.t == i)).groupby("ym").hit.mean()).round(4)
        topics.append({"topic_id": i, "key": names[i][0], "name": names[i][1], "keywords": top_words[i],
                       "n_reviews": int(m.sum()), "share": round(float(m.mean()), 4),
                       "suggestion": SUGGESTIONS.get(names[i][0], DEFAULT_SUGGESTION),
                       "samples": [{"review_id": int(neg.review_id.values[j]), "score": int(neg.score.values[j]),
                                    "summary": neg.summary.values[j], "text": neg.text.values[j][:600],
                                    "product_id": neg.product_id.values[j], "date": neg.review_date.values[j]} for j in idx],
                       "trend": [{"month": mth, "share": float(v)} for mth, v in tr.items()]})
    bundle = {"vectorizer": vec, "nmf": nmf, "names": names, "k": k}
    return bundle, topics, rt


def transform(bundle: dict, topics: list, doc: str) -> dict | None:
    w = bundle["nmf"].transform(bundle["vectorizer"].transform([doc]))[0]
    if w.max() <= 0:
        return None
    i = int(w.argmax()); t = topics[i]
    return {"topic_id": i, "name": t["name"], "weight": round(float(w[i] / (w.sum() or 1)), 3), "suggestion": t["suggestion"]}


def product_topics(state, product_id: str) -> list[dict]:
    if state.review_topics is None or state.topics is None:
        return []
    ids = state.df.loc[(state.df.product_id == product_id) & (state.df.sentiment == "neg"), "review_id"]
    rt = state.review_topics[state.review_topics.review_id.isin(ids) & (state.review_topics.topic_id >= 0)]
    if rt.empty:
        return []
    vc = rt.topic_id.value_counts()
    return [{"topic_id": int(t), "name": state.topics[int(t)]["name"], "n": int(n), "share": round(n / len(rt), 4)} for t, n in vc.items()]
