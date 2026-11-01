"""Vẽ ERD (ký hiệu chân chim) bằng HTML + SVG, chụp ảnh PNG bằng Playwright.

Chạy: python docs/diagrams/erd_build.py  → docs/erd.png
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
W, GAP = 290, 50
X = [30 + i * (W + GAP) for i in range(5)]
HDR, ROW = 46, 22

E = {  # tên: (cột, y, nhãn, nơi lưu, [(khóa, tên, kiểu)])
    "MONTHLY_METRIC": (0, 300, "Chỉ số theo tháng", "dẫn xuất từ REVIEW khi gọi API #15", [("PK", "scope_id", "str"), ("PK", "year_month", "str"), ("", "n", "int"), ("", "avg_score", "float"), ("", "neg_rate", "float"), ("", "sat_index", "float")]),
    "FORECAST": (0, 520, "Dự báo", "forecast_overall.json", [("PK", "scope_id", "str"), ("PK", "year_month", "str"), ("", "model", "str"), ("", "sat_index", "float"), ("", "lo / hi", "float")]),
    "PRODUCT_RISK": (0, 718, "Rủi ro sản phẩm", "các cột rủi ro trong products.csv", [("PK,FK", "product_id", "str"), ("", "as_of", "str"), ("", "n_3m / n_prev_3m", "int"), ("", "avg_3m / avg_prev_3m", "float"), ("", "delta", "float"), ("", "neg_rate_3m", "float"), ("", "risk_level", "str"), ("", "reason", "str")]),
    "PRODUCT": (1, 300, "Sản phẩm", "products.csv", [("PK", "product_id", "str"), ("", "n_reviews", "int"), ("", "avg_score", "float"), ("", "neg_rate", "float"), ("", "first_month / last_month", "str"), ("", "n_active_months", "int"), ("", "forecastable", "bool")]),
    "DATASET": (2, 40, "Tập dữ liệu (phiên)", "dataset_meta.json", [("PK", "dataset_version", "str"), ("", "file_name", "str"), ("", "uploaded_at", "datetime"), ("", "n_raw / n_clean", "int"), ("", "clean_log", "json"), ("", "last_full_month", "str")]),
    "REVIEW": (2, 300, "Đánh giá đã làm sạch", "reviews_clean.csv", [("PK", "review_id", "int"), ("FK", "product_id", "str"), ("", "user_key", "str (SHA-1)"), ("", "score", "int 1–5"), ("", "sentiment", "neg/neu/pos"), ("", "review_date", "date"), ("", "year_month", "str"), ("", "helpful_num / den", "int"), ("", "helpful_ratio", "float"), ("", "summary", "str"), ("", "text", "str"), ("", "n_words", "int"), ("", "dup_count", "int")]),
    "PREDICTION": (3, 40, "Kết quả dự đoán", "predictions.csv", [("PK,FK", "review_id", "int"), ("FK", "model_id", "str"), ("", "split", "train/val/test"), ("", "pred_star", "int"), ("", "p1 … p5", "float"), ("", "pred_sentiment", "str"), ("", "sat_index_pred", "float"), ("", "is_mismatch", "bool")]),
    "REVIEW_TOPIC": (3, 300, "Gán chủ đề", "review_topics.csv", [("PK,FK", "review_id", "int"), ("FK", "topic_id", "int"), ("", "topic_weight", "float")]),
    "AI_EVIDENCE": (3, 600, "Bằng chứng của nguyên nhân", "trong ai_insights.json", [("PK,FK", "insight_key", "str"), ("PK", "cause_index", "int"), ("PK,FK", "review_id", "int")]),
    "MODEL_RUN": (4, 40, "Lần huấn luyện mô hình", "model_registry.json + *.joblib", [("PK", "model_id", "str"), ("FK", "dataset_version", "str"), ("", "algo / params", "str"), ("", "n_train", "int"), ("", "f1_macro3 / f1_neg / mae", "float"), ("", "is_selected", "bool")]),
    "TOPIC": (4, 300, "Chủ đề phàn nàn", "topics.json", [("PK", "topic_id", "int"), ("", "name", "str"), ("", "keywords", "str[10]"), ("", "n_reviews", "int"), ("", "share", "float")]),
    "AI_INSIGHT": (4, 540, "Kết quả trợ lý AI (lưu đệm)", "cache/ai_insights.json", [("PK", "insight_key", "str"), ("", "scope", "product/topic"), ("", "scope_id", "str"), ("", "dataset_version", "str"), ("", "created_at", "datetime"), ("", "causes / solutions", "json"), ("", "dropped_causes", "int")]),
}


def box(name):
    c, y, _, _, rows = E[name]
    return X[c], y, W, HDR + ROW * len(rows)


def anchor(name, side, frac=0.5):
    x, y, w, h = box(name)
    return {"l": (x, y + h * frac), "r": (x + w, y + h * frac), "t": (x + w * frac, y), "b": (x + w * frac, y + h)}[side]


def row_y(name, i):
    x, y, w, h = box(name)
    return y + HDR + ROW * i + ROW / 2


# quan hệ: (điểm đầu, điểm cuối, các điểm gấp ở giữa, ký hiệu đầu, ký hiệu cuối, nhãn, vị trí nhãn)
def R():
    rv_r = anchor("REVIEW", "r")[0]
    rels = [
        (anchor("DATASET", "b"), anchor("REVIEW", "t"), [], "one", "zmany", "chứa"),
        (anchor("DATASET", "t", 0.7), anchor("MODEL_RUN", "t", 0.3), [(anchor("DATASET", "t", 0.7)[0], 16), (anchor("MODEL_RUN", "t", 0.3)[0], 16)], "one", "zmany", "huấn luyện"),
        ((X[4], row_y("MODEL_RUN", 0)), (X[3] + W, row_y("PREDICTION", 1)), [(X[4] - 25, row_y("MODEL_RUN", 0)), (X[4] - 25, row_y("PREDICTION", 1))], "one", "zmany", "sinh ra"),
        ((rv_r, row_y("REVIEW", 0)), anchor("PREDICTION", "l", 0.12), [(rv_r + 25, row_y("REVIEW", 0)), (rv_r + 25, anchor("PREDICTION", "l", 0.12)[1])], "one", "zone", "được dự đoán"),
        ((rv_r, row_y("REVIEW", 2)), (X[3], row_y("REVIEW_TOPIC", 0)), [(rv_r + 25, row_y("REVIEW", 2)), (rv_r + 25, row_y("REVIEW_TOPIC", 0))], "one", "zone", "thuộc chủ đề"),
        (anchor("TOPIC", "l", 0.5), (X[3] + W, row_y("REVIEW_TOPIC", 1)), [(X[4] - 25, anchor("TOPIC", "l", 0.5)[1]), (X[4] - 25, row_y("REVIEW_TOPIC", 1))], "one", "zmany", "gom"),
        ((rv_r, row_y("REVIEW", 10)), (X[3], row_y("AI_EVIDENCE", 2)), [(rv_r + 25, row_y("REVIEW", 10)), (rv_r + 25, row_y("AI_EVIDENCE", 2))], "one", "zmany", "là bằng chứng"),
        (anchor("AI_INSIGHT", "l", 0.25), (X[3] + W, row_y("AI_EVIDENCE", 0)), [(X[4] - 25, anchor("AI_INSIGHT", "l", 0.25)[1]), (X[4] - 25, row_y("AI_EVIDENCE", 0))], "one", "many", "dẫn chứng"),
        (anchor("TOPIC", "b"), anchor("AI_INSIGHT", "t"), [], "one", "zmany", "phân tích"),
        (anchor("PRODUCT", "r", 0.2), (X[2], row_y("REVIEW", 1)), [(X[2] - 25, anchor("PRODUCT", "r", 0.2)[1]), (X[2] - 25, row_y("REVIEW", 1))], "one", "zmany", "được đánh giá"),
        (anchor("PRODUCT", "l", 0.25), anchor("MONTHLY_METRIC", "r", 0.4), [(X[1] - 25, anchor("PRODUCT", "l", 0.25)[1]), (X[1] - 25, anchor("MONTHLY_METRIC", "r", 0.4)[1])], "one", "zmany", "theo tháng"),
        (anchor("PRODUCT", "l", 0.6), anchor("FORECAST", "r", 0.4), [(X[1] - 18, anchor("PRODUCT", "l", 0.6)[1]), (X[1] - 18, anchor("FORECAST", "r", 0.4)[1])], "one", "zmany", "dự báo"),
        (anchor("PRODUCT", "l", 0.85), anchor("PRODUCT_RISK", "r", 0.2), [(X[1] - 32, anchor("PRODUCT", "l", 0.85)[1]), (X[1] - 32, anchor("PRODUCT_RISK", "r", 0.2)[1])], "one", "zone", "mức rủi ro"),
        (anchor("PRODUCT", "b"), anchor("AI_INSIGHT", "b"), [(anchor("PRODUCT", "b")[0], 1000), (anchor("AI_INSIGHT", "b")[0], 1000)], "one", "zmany", "phân tích"),
    ]
    return rels


MARK = {
    "one": '<path d="M2,-7 L2,7 M7,-7 L7,7" />',
    "zone": '<path d="M2,-7 L2,7" /><circle cx="11" cy="0" r="4" fill="white"/>',
    "many": '<path d="M0,-7 L10,0 L0,7 M12,-7 L12,7" />',
    "zmany": '<path d="M0,-7 L10,0 L0,7" /><circle cx="15" cy="0" r="4" fill="white"/>',
}


def marker_svg(pt, toward, kind):
    import math
    ang = math.degrees(math.atan2(toward[1] - pt[1], toward[0] - pt[0]))
    return f'<g transform="translate({pt[0]},{pt[1]}) rotate({ang})" class="mk">{MARK[kind]}</g>'


def build():
    boxes = []
    for n, (c, y, vn, store, rows) in E.items():
        x, y, w, h = box(n)
        rs = "".join(f'<div class="r"><span class="k {k.replace(",", "")}">{k}</span><span class="n">{nm}</span><span class="t">{t}</span></div>' for k, nm, t in rows)
        boxes.append(f'<div class="e" style="left:{x}px;top:{y}px;width:{w}px"><div class="h"><b>{n}</b> <i>{vn}</i><div class="s">{store}</div></div>{rs}</div>')
    lines, marks, labels = [], [], []
    for a, b, mids, ka, kb, lab in R():
        pts = [a] + mids + [b]
        lines.append('<polyline points="' + " ".join(f"{p[0]},{p[1]}" for p in pts) + '"/>')
        marks.append(marker_svg(a, pts[1], ka)); marks.append(marker_svg(b, pts[-2], kb))
        # nhãn đặt ở đoạn dài nhất
        segs = list(zip(pts, pts[1:])); s = max(segs, key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
        mx, my = (s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2
        if lab not in ("chứa", "huấn luyện", "phân tích"): continue   # đường đi trong khe hẹp: không ghi nhãn (xem bảng quan hệ)
        labels.append(f'<div class="lb" style="left:{mx}px;top:{my}px">{lab}</div>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;font-family:'DejaVu Sans',sans-serif;background:#fff}}
#c{{position:relative;width:{X[4] + W + 30}px;height:1030px}}
svg{{position:absolute;left:0;top:0}} polyline{{fill:none;stroke:#5b6b82;stroke-width:1.4}}
.mk path{{fill:none;stroke:#5b6b82;stroke-width:1.4}} .mk circle{{stroke:#5b6b82;stroke-width:1.4}}
.e{{position:absolute;border:1.5px solid #1f3864;border-radius:6px;background:#fff;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.h{{background:#1f3864;color:#fff;padding:4px 8px;height:{HDR - 8}px;font-size:12.5px}} .h i{{font-style:normal;font-size:11px;color:#dce6f2}}
.s{{font-size:10px;color:#ffd166;font-family:'DejaVu Sans Mono',monospace;margin-top:1px}}
.r{{display:flex;height:{ROW}px;align-items:center;font-size:11px;border-top:1px solid #e8edf4;padding:0 6px}} .r:nth-child(odd){{background:#f6f8fb}}
.k{{width:44px;font-size:9.5px;font-weight:bold;color:#1f3864}} .k.PK{{color:#b8860b}} .k.PKFK{{color:#b8860b}}
.n{{flex:1;font-family:'DejaVu Sans Mono',monospace;color:#111}} .t{{color:#6b7280;font-size:10px}}
.lb{{position:absolute;transform:translate(-50%,-50%);background:#fff;padding:0 4px;font-size:10.5px;color:#334;font-style:italic;white-space:nowrap}}
</style></head><body><div id="c"><svg width="{X[4] + W + 30}" height="1030">{''.join(lines)}{''.join(marks)}</svg>{''.join(boxes)}{''.join(labels)}</div></body></html>"""
    p = OUT / "diagrams" / "erd.html"; p.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": X[4] + W + 30, "height": 1030}, device_scale_factor=2)
        pg.goto(p.as_uri()); pg.locator("#c").screenshot(path=str(OUT / "erd.png")); b.close()


if __name__ == "__main__":
    build()
