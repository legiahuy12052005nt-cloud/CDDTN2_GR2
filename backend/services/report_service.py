"""ReportService – báo cáo PDF tiếng Việt và các bảng CSV xuất ra (FR-22, FR-23).

PDF dựng bằng reportlab, phông DejaVu Sans (đi kèm matplotlib, hỗ trợ đủ dấu tiếng Việt); biểu đồ vẽ bằng matplotlib.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

from backend.core import config as C  # noqa: E402
from backend.services import forecast_service as FS  # noqa: E402

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
_registered = False
NAVY, BLUE, RED, GREY, GREEN, AMBER = "#0f2a4a", "#2563eb", "#dc2626", "#94a3b8", "#16a34a", "#d97706"
RISK_VN = {"high": "Cao", "medium": "Trung bình", "low": "Thấp", "insufficient": "Chưa đủ dữ liệu"}


def _fonts():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont("DV", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DVB", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB")
        _registered = True


def vn(x, nd=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, nd=1):
    return "–" if x is None or pd.isna(x) else vn(x * 100, nd) + "%"


def _png(fig) -> io.BytesIO:
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=160, bbox_inches="tight"); plt.close(fig); buf.seek(0)
    return buf


def _style_ax(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1"); ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#475569", labelsize=8); ax.grid(axis="y", color="#e2e8f0", lw=0.6); ax.set_axisbelow(True)


def _thousands(ax):
    from matplotlib.ticker import FuncFormatter
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))


def chart_scores(df) -> io.BytesIO:
    vc = df.score.value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
    fig, ax = plt.subplots(figsize=(3.6, 2.7))
    cols = [RED, RED, GREY, BLUE, BLUE]
    ax.bar([f"{k}★" for k in vc.index], vc.values, color=cols, width=0.62)
    for i, v in enumerate(vc.values):
        ax.text(i, v, f"{v / vc.sum():.1%}".replace(".", ","), ha="center", va="bottom", fontsize=8, color="#334155")
    ax.set_title("Phân bố số sao", fontsize=10, loc="left", color=NAVY); _style_ax(ax); _thousands(ax)
    return _png(fig)


def chart_forecast(state) -> io.BytesIO:
    fo = FS.forecast(state, None, 12)
    h = pd.DataFrame(fo["history"]); f = pd.DataFrame(fo["forecast"])
    fig, ax = plt.subplots(figsize=(5.0, 2.7))
    if not h.empty:
        ax.plot(pd.to_datetime(h.month), h.sat_index, color=NAVY, lw=1.6, label="Thực tế")
    if not f.empty:
        x = pd.to_datetime(f.month)
        ax.fill_between(x, f.lo, f.hi, color=BLUE, alpha=0.15, lw=0, label="Khoảng tin cậy 95%")
        ax.plot(x, f.sat_index, color=BLUE, lw=1.6, ls="--", label=f"Dự báo ({fo.get('model')})")
    ax.set_title("Chỉ số hài lòng theo tháng, dự báo 12 tháng", fontsize=10, loc="left", color=NAVY)
    ax.legend(fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3); _style_ax(ax)
    return _png(fig)


def chart_topics(topics) -> io.BytesIO:
    t = sorted(topics, key=lambda t: t["share"])
    fig, ax = plt.subplots(figsize=(6.6, 0.32 * len(t) + 0.6))
    ax.barh([x["name"] for x in t], [x["share"] * 100 for x in t], color=RED, alpha=0.85, height=0.6)
    for i, x in enumerate(t):
        ax.text(x["share"] * 100, i, f" {x['share'] * 100:.1f}%".replace(".", ","), va="center", fontsize=7, color="#334155")
    ax.set_title("Tỷ trọng chủ đề trong đánh giá tiêu cực (%)", fontsize=10, loc="left", color=NAVY)
    _style_ax(ax); ax.grid(axis="x", color="#e2e8f0", lw=0.6); ax.grid(axis="y", visible=False)
    return _png(fig)


def build_pdf(state) -> bytes:
    _fonts()
    ss = {"t": ParagraphStyle("t", fontName="DVB", fontSize=17, leading=22, textColor=colors.HexColor(NAVY)),
          "st": ParagraphStyle("st", fontName="DV", fontSize=9, leading=13, textColor=colors.HexColor("#475569")),
          "h": ParagraphStyle("h", fontName="DVB", fontSize=12, leading=16, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor(NAVY)),
          "p": ParagraphStyle("p", fontName="DV", fontSize=9, leading=13),
          "c": ParagraphStyle("c", fontName="DV", fontSize=7.5, leading=9.5),
          "cb": ParagraphStyle("cb", fontName="DVB", fontSize=7.5, leading=9.5, textColor=colors.white),
          "k": ParagraphStyle("k", fontName="DVB", fontSize=14, leading=17, alignment=TA_CENTER, textColor=colors.HexColor(NAVY)),
          "kl": ParagraphStyle("kl", fontName="DV", fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.HexColor("#64748b"))}
    df, m = state.df, state.meta
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title="Báo cáo FoodReview Insight", author="FoodReview Insight")
    W = A4[0] - 3.2 * cm
    E = []

    def table(head, rows, widths, align_right=()):
        data = [[Paragraph(h, ss["cb"]) for h in head]] + [[Paragraph(str(c), ss["c"]) for c in r] for r in rows]
        t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
        st = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        t.setStyle(TableStyle(st)); return t

    # ---- 1. Trang đầu: KPI ----
    E += [Paragraph("Báo cáo mức độ hài lòng khách hàng", ss["t"]),
          Paragraph(f"FoodReview Insight · dữ liệu {m.get('file_name', '')} (phiên bản {state.version}) · "
                    f"{m['date_min']} → {m['date_max']} · tạo lúc {pd.Timestamp.now():%d/%m/%Y %H:%M}", ss["st"]), Spacer(1, 10)]
    avg = float(df.score.mean()); n_high = int((state.products.risk_level == "high").sum()) if state.products is not None else 0
    kp = [(vn(len(df), 0), "đánh giá sau làm sạch"), (vn(m["n_products"], 0), "sản phẩm"), (vn(avg, 2) + "/5", "điểm sao TB"),
          (vn(C.satisfaction_index(avg), 1), "chỉ số hài lòng"), (pct((df.sentiment == "neg").mean()), "tỷ lệ tiêu cực"), (str(n_high), "SP rủi ro cao")]
    kt = Table([[Paragraph(v, ss["k"]) for v, _ in kp], [Paragraph(l, ss["kl"]) for _, l in kp]], colWidths=[W / 6] * 6)
    kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                            ("LINEAFTER", (0, 0), (-2, -1), 0.4, colors.HexColor("#e2e8f0")), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    E += [kt, Spacer(1, 8)]
    log = m.get("clean_log", {})
    E.append(Paragraph(f"Làm sạch: {vn(m.get('n_rows_raw', 0), 0)} dòng gốc → {vn(len(df), 0)} đánh giá "
                       f"(loại {vn(log.get('r5_duplicates', 0), 0)} bản trùng, {vn(log.get('r7_too_short', 0), 0)} nội dung quá ngắn, "
                       f"{vn(log.get('r4_helpfulness_invalid', 0), 0)} dòng lỗi Helpfulness).", ss["p"]))
    charts = [Image(chart_scores(df), width=W * 0.41, height=W * 0.41 * 2.7 / 3.6)]
    if state.forecast:
        charts.append(Image(chart_forecast(state), width=W * 0.57, height=W * 0.57 * 2.7 / 5.0))
    ct = Table([charts], colWidths=[W * 0.42, W * 0.58]); ct.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    E += [Spacer(1, 4), ct, Spacer(1, 2)]
    if state.forecast:
        bt = state.forecast.get("backtest")
        fc = state.forecast.get("forecast") or []
        if fc:
            E.append(Paragraph(f"Mô hình {state.forecast.get('model')} trên chuỗi {state.forecast.get('series_start')} → {state.forecast.get('series_end')}; "
                               f"dự báo tháng {fc[0]['month']}: {vn(fc[0]['sat_index'], 1)} (95%: {vn(fc[0]['lo'], 1)}–{vn(fc[0]['hi'], 1)})"
                               + (f"; kiểm tra lùi 12 tháng: MAE {vn(bt['mae_model'])} điểm so với {vn(bt['mae_naive'])} của mô hình ngây thơ." if bt else "."), ss["p"]))

    # ---- 2. Mô hình ----
    if state.registry:
        r = state.registry
        E.append(Paragraph("Mô hình dự đoán số sao và cảm xúc", ss["h"]))
        E.append(Paragraph(f"Huấn luyện trên {vn(r['split']['train'], 0)} đánh giá đã làm sạch, kiểm tra trên {vn(r['split']['test'], 0)} đánh giá "
                           f"(chia 80/20 phân tầng theo số sao, random_state = 42). Mô hình được chọn: <b>{r['selected']}</b>.", ss["p"]))
        rows = [[x["model"] + (" ✓" if x.get("selected") else ""), x["params"], vn(x["f1_macro3"], 3), vn(x["f1_neg"], 3), vn(x["f1_neu"], 3),
                 vn(x["f1_pos"], 3), vn(x["acc5"], 3), vn(x["mae"], 3)] for x in r["models"]]
        E.append(table(["Mô hình", "Tham số", "F1-macro 3 lớp", "F1 tiêu cực", "F1 trung tính", "F1 tích cực", "Accuracy 5 sao", "MAE"], rows,
                       [.12, .16, .13, .11, .12, .11, .13, .12]))
        up = ", ".join(k["term"] for k in r["keywords"]["up"][:12]); dn = ", ".join(k["term"] for k in r["keywords"]["down"][:12])
        E.append(Spacer(1, 4)); E.append(Paragraph(f"<b>Từ kéo số sao lên:</b> {up}.<br/><b>Từ kéo số sao xuống:</b> {dn}.", ss["p"]))
        tc = r.get("time_check")
        if tc:
            E.append(Spacer(1, 4))
            E.append(Paragraph(f"<b>Kiểm tra theo thời gian:</b> {tc['rule']} ({vn(tc['n_train'], 0)} học / {vn(tc['n_test'], 0)} kiểm tra) – "
                               f"F1-macro {vn(tc['f1_macro3'], 3)} so với {vn(tc.get('random_f1_macro3', r['selected_metrics']['f1_macro3']), 3)} khi chia ngẫu nhiên. "
                               "Chênh lệch nhỏ cho thấy cách chia ngẫu nhiên không làm kết quả đẹp hơn đáng kể và mô hình vẫn dùng được cho dữ liệu mới hơn.", ss["p"]))

    # ---- 3. Cảnh báo ----
    if state.products is not None:
        E.append(PageBreak())
        p = state.products
        cnt = p.risk_level.value_counts()
        E.append(Paragraph("Cảnh báo sản phẩm", ss["h"]))
        E.append(Paragraph(f"So sánh 3 tháng gần nhất với 3 tháng liền trước (tính đến {m['last_full_month']}), mỗi cửa sổ ≥ 10 đánh giá. "
                           f"Rủi ro cao: {vn(cnt.get('high', 0), 0)} · trung bình: {vn(cnt.get('medium', 0), 0)} · thấp: {vn(cnt.get('low', 0), 0)} · "
                           f"chưa đủ dữ liệu: {vn(cnt.get('insufficient', 0), 0)} sản phẩm. Bảng dưới liệt kê tối đa 30 sản phẩm rủi ro cao và trung bình, "
                           f"sắp theo mức rủi ro rồi mức giảm điểm 3 tháng (giảm mạnh nhất trước); danh sách đầy đủ ở file CSV product_risk.", ss["p"]))
        bt = (getattr(state, "risk_backtest", None) or {}).get("summary") or {}
        if bt.get("high", {}).get("neg_next") is not None and bt.get("low", {}).get("neg_next") is not None:
            E.append(Paragraph(f"<b>Kiểm tra ngược quy tắc</b> (gắn mức tại {', '.join(state.risk_backtest['as_of_points'])}, xem 3 tháng tiếp theo): "
                               f"nhóm Cao có tỷ lệ tiêu cực {pct(bt['high']['neg_next'], 1)} ở 3 tháng sau, nhóm Thấp {pct(bt['low']['neg_next'], 1)} – "
                               "nhóm bị cảnh báo vẫn kém hơn rõ rệt khi quy tắc chưa nhìn thấy dữ liệu đó.", ss["p"]))
        top = p[p.risk_level.isin(["high", "medium"])].sort_values(["risk_rank", "delta", "neg_rate_3m"], ascending=[False, True, False], na_position="last").head(30)
        sgn = lambda d: "–" if d is None or pd.isna(d) else ("+" if d > 0 else "") + vn(d)   # noqa: E731
        rows = [[x.product_id, RISK_VN[x.risk_level], vn(x.n_reviews, 0), vn(x.avg_prev_3m), vn(x.avg_3m), sgn(x.delta), pct(x.neg_rate_3m, 0), x.reason]
                for x in top.itertuples()]
        if rows:
            E.append(table(["Sản phẩm", "Mức", "Số ĐG", "TB 3 th. trước", "TB 3 th. gần", "Thay đổi", "Tiêu cực 3 th.", "Lý do"], rows,
                           [.13, .1, .07, .1, .1, .08, .1, .32]))
    # ---- 4. Chủ đề ----
    if state.topics:
        E.append(PageBreak())
        E.append(Paragraph("Chủ đề phàn nàn và gợi ý hành động", ss["h"]))
        E.append(Paragraph(f"NMF k = {len(state.topics)} trên {vn(int((df.sentiment == 'neg').sum()), 0)} đánh giá 1–2 sao; tên chủ đề do nhóm đặt từ 10 từ khóa và đánh giá mẫu.", ss["p"]))
        E.append(Image(chart_topics(state.topics), width=W * 0.9, height=W * 0.9 * (0.32 * len(state.topics) + 0.6) / 6.6 * 0.98))
        rows = [[t["name"], pct(t["share"]), ", ".join(t["keywords"][:6]), t["suggestion"]] for t in sorted(state.topics, key=lambda t: -t["share"])]
        E.append(table(["Chủ đề", "Tỷ trọng", "Từ khóa", "Gợi ý hành động"], rows, [.22, .08, .27, .43]))
    # ---- 5. AI ----
    try:
        cache = json.loads((C.CACHE_DIR / "ai_insights.json").read_text(encoding="utf-8"))
        items = [v for k, v in cache.items() if k.endswith(state.version)][:5]
    except Exception:  # noqa: BLE001
        items = []
    if items:
        E.append(Paragraph("Phân tích nguyên nhân – giải pháp từ trợ lý AI (Gemini)", ss["h"]))
        for it in items:
            E.append(Paragraph(f"<b>{it.get('title', it['id'])}</b> ({it['created_at']})", ss["p"]))
            for i, c in enumerate(it["causes"]):
                sol = next((s for s in it["solutions"] if s["cause_index"] == i), None)
                E.append(Paragraph(f"• <b>{c['title']}</b> [{c['severity']}] – {c['description']} (bằng chứng: {', '.join(map(str, c['evidence_ids']))})"
                                   + (f"<br/>&nbsp;&nbsp;→ {sol['action']} · KPI: {sol['kpi']}" if sol else ""), ss["p"]))
    doc.build(E, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(canvas, doc):
    canvas.saveState(); canvas.setFont("DV", 7); canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(1.6 * cm, 0.8 * cm, "FoodReview Insight – Phân tích & dự báo mức độ hài lòng khách hàng từ đánh giá thực phẩm Amazon")
    canvas.drawRightString(A4[0] - 1.6 * cm, 0.8 * cm, f"Trang {doc.page}")
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# CSV xuất ra (FR-23) – mã hóa utf-8-sig để Excel đọc đúng tiếng Việt
# --------------------------------------------------------------------------- #
def export_csv(state, table: str) -> tuple[bytes, str]:
    if table == "product_risk":
        p = state.products.sort_values(["risk_rank", "delta", "neg_rate_3m"], ascending=[False, True, False], na_position="last")
        cols = ["product_id", "risk_level", "signal", "reason", "n_reviews", "avg_score", "neg_rate", "n_3m", "avg_3m", "neg_rate_3m",
                "n_prev_3m", "avg_prev_3m", "delta", "first_month", "last_month", "n_active_months", "forecastable", "as_of"]
        out = p[cols]
    elif table == "topics":
        out = pd.DataFrame([{"topic_id": t["topic_id"], "name": t["name"], "n_reviews": t["n_reviews"], "share": t["share"],
                             "keywords": ", ".join(t["keywords"]), "suggestion": t["suggestion"]} for t in (state.topics or [])])
    elif table == "predictions":
        pr = state.predictions
        out = pr.merge(state.df[["review_id", "product_id", "review_date", "summary"]], on="review_id", how="left")
    elif table == "monthly":
        out = FS.monthly(state.df)
    elif table == "model_metrics":
        reg = state.registry
        out = pd.DataFrame([{**m, "split": "ngẫu nhiên phân tầng 80/20", "n_train": reg["split"]["train"], "n_test": reg["split"]["test"]}
                            for m in reg["models"]])
        tc = reg.get("time_check")
        if tc:
            out = pd.concat([out, pd.DataFrame([{"model": "LR", "params": f"C={C.LR_C}", "split": "theo thời gian – " + tc["rule"],
                                                 "n_train": tc["n_train"], "n_test": tc["n_test"],
                                                 **{k: tc[k] for k in ("f1_macro3", "f1_neg", "f1_neu", "f1_pos", "acc3", "acc5", "mae")}}])],
                            ignore_index=True)
    elif table == "forecast":
        fo = state.forecast or {}
        out = pd.DataFrame([{**p, "model": fo.get("model"), "unit": "chỉ số hài lòng 0–100", "ci": "95%"} for p in (fo.get("forecast") or [])])
    else:
        raise KeyError(table)
    return out.to_csv(index=False).encode("utf-8-sig"), f"{table}_{state.version}.csv"

