"""Sinh wireframe 10 màn hình (độ trung thực trung bình, thang xám + 1 màu nhấn) từ số liệu thật.

Chạy sau notebook 01–05: python docs/diagrams/wireframes_build.py → docs/wireframes/wf_XX.png
Ký hiệu ① ② … trên hình ứng với bảng đặc tả thành phần giao diện trong tài liệu thiết kế (mục 7).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "notebooks" / "outputs"
OUT = ROOT / "docs" / "wireframes"; OUT.mkdir(parents=True, exist_ok=True)
eda = json.loads((NB / "eda_stats.json").read_text()); mr = json.loads((NB / "model_results.json").read_text())
tr = json.loads((NB / "topic_results.json").read_text()); fr = json.loads((NB / "forecast_results.json").read_text())
rk = json.loads((NB / "risk_results.json").read_text())


def vn(x, d=0):
    s = f"{x:,.{d}f}"; return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1): return vn(x * 100, d) + "%"


sel = mr["selected"]; T = mr["test"]
TABS = ["Tổng quan", "Phân tích (EDA)", "Mô hình ML", "Tự nhập dự đoán", "Sản phẩm & cảnh báo", "Chủ đề phàn nàn", "Dự báo", "Trợ lý AI", "Báo cáo"]
CSS = """
*{box-sizing:border-box} body{margin:0;font-family:'DejaVu Sans',sans-serif;font-size:13px;color:#222;background:#fff}
.frame{width:1120px;border:2px solid #333;border-radius:10px;overflow:hidden;position:relative;background:#fafafa}
.top{height:46px;background:#2b2b2b;color:#fff;display:flex;align-items:center;padding:0 16px;gap:14px}
.top b{font-size:15px} .badge{background:#444;border-radius:12px;padding:3px 10px;font-size:11.5px;color:#ddd}
.top .sp{flex:1} .btn{border:1.5px solid #555;border-radius:6px;padding:5px 12px;background:#fff;font-size:12px;display:inline-block}
.btn.p{background:#2a78d6;border-color:#2a78d6;color:#fff} .top .btn{background:#3a3a3a;color:#eee;border-color:#666}
.tabs{display:flex;gap:2px;background:#e6e6e6;padding:6px 10px 0} .tab{padding:7px 12px;border-radius:6px 6px 0 0;font-size:12px;color:#555;background:#efefef}
.tab.on{background:#fafafa;color:#111;font-weight:bold;border:1px solid #ccc;border-bottom:none}
.body{padding:18px 18px 70px 22px} .row{display:flex;gap:12px;margin-bottom:12px} .col{flex:1}
.card{background:#fff;border:1.5px solid #bbb;border-radius:8px;padding:10px 12px;position:relative}
.card h4{margin:0 0 8px;font-size:13px} .kpi .v{font-size:22px;font-weight:bold} .kpi .l{font-size:11.5px;color:#666}
.ph{background:repeating-linear-gradient(45deg,#eee,#eee 8px,#f6f6f6 8px,#f6f6f6 16px);border:1px dashed #aaa;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#777;font-size:12px;text-align:center;padding:6px}
table{border-collapse:collapse;width:100%;font-size:11.5px} th{background:#e9e9e9;text-align:left;padding:5px 6px;border:1px solid #ccc} td{padding:4px 6px;border:1px solid #ddd;background:#fff}
.inp{border:1.5px solid #999;border-radius:6px;background:#fff;padding:6px 8px;color:#888;font-size:12px}
.ann{position:absolute;width:24px;height:24px;border-radius:50%;background:#eb6834;color:#fff;font-weight:bold;font-size:13px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 3px #fff;z-index:5}
.risk{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
.hi{background:#fde2e2;color:#a61b1b} .me{background:#fff1d0;color:#8a5a00} .lo{background:#e3eefc;color:#1c4f95}
.bar{height:12px;background:#2a78d6;border-radius:3px} .bar.r{background:#e34948} .chip{display:inline-block;border:1px solid #aaa;border-radius:12px;padding:2px 8px;margin:2px;font-size:11px;background:#fff}
.fab{position:absolute;right:18px;bottom:16px;width:48px;height:48px;border-radius:50%;background:#2a78d6;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 2px 6px rgba(0,0,0,.3)}
.muted{color:#777;font-size:11.5px} .neg{background:#fbd5d5} .pos{background:#d6e6fb}
.step{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px} .dot{width:14px;height:14px;border-radius:50%;border:2px solid #999}
.dot.d{background:#1baf7a;border-color:#1baf7a} .dot.r{background:#fff;border-color:#2a78d6;border-width:4px}
"""


def ann(n, x, y): return f'<div class="ann" style="left:{x}px;top:{y}px">{n}</div>'


def shell(tab, inner, annots="", fab=True, upload=False):
    tabs = "" if upload else '<div class="tabs">' + "".join(f'<div class="tab{" on" if t == tab else ""}">{t}</div>' for t in TABS) + "</div>"
    right = '<span class="sp"></span><span class="btn">Hướng dẫn</span>' if upload else \
        f'<span class="badge">Dữ liệu: Reviews.csv · {vn(eda["meta"]["n_reviews"])} đánh giá sạch · đến {eda["meta"]["last_full_month"]}</span><span class="sp"></span><span class="btn">Đổi file</span>'
    return f'<div class="frame"><div class="top"><b>FoodReview Insight</b>{right}</div>{tabs}<div class="body">{inner}</div>{"<div class=fab>💬</div>" if fab else ""}{annots}</div>'


S = {}
q = eda["quality"]; cl = eda["clean_log"]
S["01_upload"] = shell(None, f"""
<div class="row"><div class="col card" style="height:170px"><h4>Tải dữ liệu đánh giá</h4>
<div class="ph" style="height:96px">⇪ Kéo-thả file .csv vào đây hoặc <u>chọn file</u><br>Cột bắt buộc: Score, Time, Text · tối đa 400 MB</div>
<div style="margin-top:8px"><span class="btn">Dùng dữ liệu mẫu (100.000 dòng)</span></div></div>
<div class="card" style="width:360px;height:170px"><h4>Tiến trình xử lý</h4>
<div class="step"><span class="dot d"></span>Kiểm tra cấu trúc</div><div class="step"><span class="dot d"></span>Làm sạch R1–R9</div>
<div class="step"><span class="dot d"></span>Thống kê EDA</div><div class="step"><span class="dot r"></span><b>Huấn luyện mô hình – 62%</b></div>
<div class="step"><span class="dot"></span>Chủ đề · Dự báo · Cảnh báo</div></div></div>
<div class="card" style="margin-bottom:12px;background:#fff4f4;border-color:#e34948"><b style="color:#a61b1b">✖ Thiếu cột bắt buộc: Text</b> <span class="muted">— file chưa được xử lý; hãy kiểm tra tên cột (ví dụ trạng thái lỗi)</span></div>
<div class="row"><div class="card" style="width:400px"><h4>Báo cáo chất lượng dữ liệu</h4><table>
<tr><td>Số dòng / số cột</td><td>{vn(q['n_rows'])} / 10</td></tr><tr><td>Bản ghi trùng (UserId, Time, Text)</td><td>{vn(q['n_duplicates'])}</td></tr>
<tr><td>Thiếu Summary / ProfileName</td><td>{q['missing_by_column']['Summary']} / {q['missing_by_column']['ProfileName']}</td></tr>
<tr><td>Helpfulness bất hợp lệ</td><td>{q['n_helpfulness_invalid']}</td></tr><tr><td>Khoảng thời gian</td><td>08/10/1999 – 26/10/2012</td></tr>
<tr><td><b>Còn lại sau làm sạch</b></td><td><b>{vn(cl['n_clean'])}</b></td></tr></table></div>
<div class="col card"><h4>Xem trước 20 dòng đầu</h4><table><tr><th>Id</th><th>ProductId</th><th>Score</th><th>Time</th><th>Summary</th><th>Text</th></tr>
<tr><td>1</td><td>B001E4KFG0</td><td>5</td><td>2011-04-27</td><td>Good Quality Dog Food</td><td>I have bought several of the Vitality…</td></tr>
<tr><td>2</td><td>B00813GRG4</td><td>1</td><td>2012-09-07</td><td>Not as Advertised</td><td>Product arrived labeled as Jumbo…</td></tr>
<tr><td>3</td><td>B000LQOCH0</td><td>4</td><td>2008-08-18</td><td>"Delight" says it all</td><td>This is a confection that has been…</td></tr>
<tr><td colspan=6 class="muted">… 17 dòng nữa · ProfileName đã ẩn</td></tr></table></div></div>""",
    ann(1, 40, 64) + ann(2, 40, 196) + ann(3, 760, 64) + ann(4, 40, 248) + ann(5, 40, 302) + ann(6, 430, 302), fab=False, upload=True)

k = eda
n_high = rk["levels_2012_09"]["high"]
kpis = [("Tổng đánh giá", vn(k["meta"]["n_reviews"])), ("Sản phẩm", vn(k["meta"]["n_products"])), ("Người dùng", vn(k["meta"]["n_users"])),
        ("Điểm sao TB", vn(k["score_mean_clean"], 2)), ("Tỷ lệ tiêu cực", pct(k["sentiment_clean"]["neg"] / k["meta"]["n_reviews"])),
        ("F1-macro mô hình", vn(T[sel]["f1_macro3"], 3)), ("SP rủi ro cao", str(n_high))]
S["02_overview"] = shell("Tổng quan", '<div class="row">' + "".join(f'<div class="col card kpi"><div class="l">{l}</div><div class="v">{v}</div></div>' for l, v in kpis) + "</div>" + f"""
<div class="row"><div class="col card"><h4>Điểm sao TB và tỷ lệ tiêu cực theo tháng</h4><div class="ph" style="height:230px">Biểu đồ đường (Recharts) · 2 khung chung trục thời gian<br>Tooltip: tháng · số đánh giá · điểm TB · tỷ lệ tiêu cực</div></div>
<div class="card" style="width:330px"><h4>Phân bố số sao</h4><div class="ph" style="height:230px">Biểu đồ cột 1–5 sao<br>màu theo nhãn cảm xúc</div></div></div>
<div class="card"><h4>Cảnh báo nhanh – sản phẩm rủi ro Cao (tháng {rk['top_high'][0]['as_of'] if 'as_of' in rk['top_high'][0] else '2012-09'})</h4><table><tr><th>Mã SP</th><th>ĐTB 3 tháng</th><th>Δ so với 3 tháng trước</th><th>Tỷ lệ tiêu cực</th><th>Lý do</th></tr>""" +
    "".join(f"<tr><td>{r['product_id']}</td><td>{vn(r['avg_3m'], 2)}</td><td>{vn(r['delta'], 2)}</td><td>{pct(r['neg_rate_3m'], 0)}</td><td><span class='risk hi'>▲ Cao</span> {r['reason']}</td></tr>" for r in sorted(rk["top_high"], key=lambda r: r["delta"])[:3]) + "</table><div class='muted' style='margin-top:4px'>Cùng mức rủi ro: sản phẩm giảm điểm mạnh nhất đứng trước</div></div>" +
    f"""<div class="card" style="margin-top:12px"><h4>Giới hạn cần biết khi đọc kết quả</h4><div class="muted">Nhãn cảm xúc suy ra từ số sao · dữ liệu đến 26/10/2012, dự báo và cảnh báo dừng ở tháng trọn vẹn {eda['meta']['last_full_month']} ·
chỉ sản phẩm có ≥ 10 đánh giá mỗi cửa sổ 3 tháng mới gắn được mức rủi ro · chủ đề NMF là nhóm từ khóa thống kê, tên do nhóm đặt · trợ lý AI đọc tối đa 30 đánh giá, mỗi nguyên nhân kèm ID bằng chứng</div></div>""",
    ann(1, 6, 112) + ann(2, 6, 186) + ann(3, 780, 186) + ann(4, 6, 470))

S["03_eda"] = shell("Phân tích (EDA)", """
<div class="card" style="margin-bottom:12px;display:flex;gap:10px;align-items:center"><b>Bộ lọc</b><span class="inp">Từ tháng: 2007-01</span><span class="inp">Đến tháng: 2012-09</span>
<span class="inp" style="width:170px">Mã sản phẩm…</span><span class="inp">Cảm xúc: Tất cả ▾</span><span class="inp">Số sao: Tất cả ▾</span><span class="btn p">Áp dụng</span><span class="btn">Xóa lọc</span></div>
<div class="row"><div class="col card"><h4>Phân bố số sao</h4><div class="ph" style="height:150px">Cột 1–5 sao</div></div>
<div class="col card"><h4>Độ dài đánh giá theo số sao</h4><div class="ph" style="height:150px">Hộp Q1–Q3 + trung vị (số từ)</div></div></div>
<div class="row"><div class="col card"><h4>Từ khóa đặc trưng: Tiêu cực | Tích cực</h4><div class="ph" style="height:170px">2 biểu đồ thanh ngang (log-odds)<br>not · disappointed · bad · waste … | great · love · best · delicious …</div></div>
<div class="col card"><h4>10 sản phẩm nhiều đánh giá nhất</h4><table><tr><th>Mã SP</th><th>Số đánh giá</th></tr>""" +
    "".join(f"<tr><td>{p}</td><td>{vn(n)}</td></tr>" for p, n in list(eda["products"]["top10"].items())[:5]) + "<tr><td colspan=2 class=muted>… 5 dòng nữa</td></tr></table></div></div>",
    ann(1, 6, 104) + ann(2, 6, 160) + ann(3, 560, 160) + ann(4, 6, 336) + ann(5, 560, 336))

rows = [("Luôn 5 sao (B0)", mr["B0_majority"], "–")] + [(n, T[k2], T[k2]["param"]) for k2, n in [("LR", "Logistic Regression"), ("NB", "Multinomial NB"), ("SVM", "Linear SVM (hiệu chỉnh)")]]
S["04_model"] = shell("Mô hình ML", f"""
<div class="card" style="margin-bottom:12px"><b>Cách tách dữ liệu:</b> bỏ trùng → train {vn(mr['split']['train'])} · validation {vn(mr['split']['val'])} · test {vn(mr['split']['test'])} (phân tầng theo số sao, random_state = 42) · ứng dụng huấn luyện trên mẫu 100.000 dòng</div>
<div class="row"><div class="col card"><h4>So sánh mô hình trên tập test</h4><table><tr><th>Mô hình</th><th>Tham số</th><th>F1-macro 3 lớp</th><th>F1 Tiêu cực</th><th>MAE sao</th><th>Accuracy 5 sao</th></tr>""" +
    "".join(f"<tr{' style=font-weight:bold' if n.startswith('Logistic') and sel == 'LR' else ''}><td>{n}{' ✔ chọn' if (n.startswith('Logistic') and sel == 'LR') else ''}</td><td>{p}</td><td>{vn(r['f1_macro3'], 3)}</td><td>{vn(r['f1_neg'], 3)}</td><td>{vn(r['mae'], 3)}</td><td>{vn(r['acc5'], 3)}</td></tr>" for n, r, p in rows) + """</table></div>
<div class="card" style="width:300px"><h4>Ma trận nhầm lẫn (3 lớp)</h4><div class="ph" style="height:150px">Ô màu theo tỷ lệ hàng<br>Thực tế × Dự đoán</div></div></div>
<div class="row"><div class="col card"><h4>Từ khóa làm tăng / giảm số sao</h4><div class="ph" style="height:150px">Thanh ngang 2 phía: 15 từ ↑ | 15 từ ↓ (hệ số mô hình)</div></div>
<div class="col card"><h4>Đánh giá lệch (5 sao nhưng nội dung chê, P ≥ 0,8)</h4><table><tr><th>Id</th><th>Sao</th><th>P(Tiêu cực)</th><th>Tiêu đề</th></tr>""" +
    "".join(f"<tr><td>{e['review_id']}</td><td>5</td><td>≥ 0,80</td><td>{str(e['summary'])[:38]}</td></tr>" for e in mr["mismatch_examples"][:3]) + "</table></div></div>" +
    f"""<div class="card"><h4>Kết quả có đáng tin không? – kiểm tra theo thời gian</h4><table><tr><th>Cách chia</th><th>Học / kiểm tra</th><th>F1-macro 3 lớp</th><th>F1 Tiêu cực</th></tr>
<tr><td>Ngẫu nhiên, phân tầng theo số sao (tập test 20%)</td><td>{vn(mr['split']['train'] + mr['split']['val'])} / {vn(mr['split']['test'])}</td><td>{vn(T[sel]['f1_macro3'], 3)}</td><td>{vn(T[sel]['f1_neg'], 3)}</td></tr>
<tr><td>Theo thời gian: học trên đánh giá trước 01/2012, kiểm tra năm 2012</td><td>{vn(100000)} / {vn(mr['out_of_time_2012']['n_test'])}</td><td>{vn(mr['out_of_time_2012']['f1_macro3'], 3)}</td><td>{vn(mr['out_of_time_2012']['f1_neg'], 3)}</td></tr></table>
<div class="muted" style="margin-top:4px">Chênh lệch ≤ 0,02 → cách chia ngẫu nhiên không làm kết quả đẹp hơn đáng kể · ứng dụng lặp lại kiểm tra này ở mỗi lần xử lý dữ liệu; dùng bộ đầy đủ thì hiện thêm số liệu notebook để đối chiếu</div></div>""",
    ann(1, 6, 104) + ann(2, 6, 160) + ann(3, 800, 160) + ann(4, 6, 350) + ann(5, 560, 350))

S["05_predict"] = shell("Tự nhập dự đoán", """
<div class="row"><div class="card" style="width:470px"><h4>Nhập đánh giá</h4><div class="muted">Nội dung đánh giá (tiếng Anh, tối thiểu 3 từ) *</div>
<div class="inp" style="height:110px;color:#222">The coffee arrived stale and the box was crushed. Very disappointed, will not order again.</div>
<div class="muted" style="margin-top:6px">Tiêu đề (tùy chọn)</div><div class="inp" style="color:#222">Stale coffee</div>
<div class="muted" style="margin-top:6px">Mã sản phẩm (tùy chọn)</div><div class="inp">B007JFMH8M</div>
<div style="margin-top:10px"><span class="btn p">Dự đoán</span> <span class="btn">Đặt lại</span> <span class="muted">· phản hồi ≤ 1 giây</span></div></div>
<div class="col card"><h4>Kết quả</h4><div class="row" style="margin:0"><div class="col"><div class="muted">Số sao dự đoán</div><div style="font-size:30px;font-weight:bold">★ 1</div></div>
<div class="col"><div class="muted">Cảm xúc</div><div style="font-size:20px;font-weight:bold;color:#a61b1b">Tiêu cực · 88%</div></div><div class="col"><div class="muted">Chỉ số hài lòng</div><div style="font-size:24px;font-weight:bold">9 / 100</div></div></div>
<div style="margin-top:8px">""" + "".join(f'<div style="display:flex;align-items:center;gap:6px;margin:2px 0"><span style="width:44px">{s} sao</span><div class="bar{" r" if s <= 2 else ""}" style="width:{int(p * 330)}px"></div><span class="muted">{int(p * 100)}%</span></div>' for s, p in [(1, .71), (2, .17), (3, .06), (4, .03), (5, .03)]) + """</div>
<div class="tok" style="margin-top:8px"><b>Từ ảnh hưởng:</b> The coffee arrived <span class="neg">stale</span> and the box was <span class="neg">crushed</span>. Very <span class="neg">disappointed</span>, will <span class="neg">not order</span> again.</div>
<div style="margin-top:8px" class="card"><b>Chủ đề gần nhất:</b> Hàng cũ, hết hạn, bao bì hỏng khi nhận<br><b>Gợi ý:</b> kiểm tra hạn sử dụng khi nhập kho, quy cách đóng gói và đơn vị vận chuyển</div></div></div>
<div class="card"><h4>Lịch sử dự đoán trong phiên</h4><table><tr><th>#</th><th>Nội dung (rút gọn)</th><th>Sao</th><th>Cảm xúc</th><th>Chỉ số</th></tr>
<tr><td>2</td><td>The coffee arrived stale and the box…</td><td>1</td><td>Tiêu cực</td><td>9</td></tr><tr><td>1</td><td>Great taste, my kids love these bars…</td><td>5</td><td>Tích cực</td><td>94</td></tr></table></div>""",
    ann(1, 6, 104) + ann(2, 498, 104) + ann(3, 498, 196) + ann(4, 498, 318) + ann(5, 498, 352) + ann(6, 6, 470))

items = sorted(rk["top_high"], key=lambda r: r["delta"])[:4]
# kiểm tra ngược (notebook 05): gộp hai mốc gắn mức, tỷ lệ tiêu cực 3 tháng tiếp theo theo từng mức
_bt = {}
for b_ in rk["backtest"]:
    a_ = _bt.setdefault(b_["risk_level"], [0, 0.0]); a_[0] += b_["san_pham"]; a_[1] += b_["san_pham"] * b_["neg_next"]
BT = {k_: (v_[0], v_[1] / v_[0]) for k_, v_ in _bt.items()}
TAG = "<span class='chip' style='border-color:#e34948;color:#a61b1b;font-weight:bold'>Đang giảm điểm</span>"
TAG2 = "<span class='chip' style='border-color:#eda100;color:#8a5a00;font-weight:bold'>Tiêu cực kéo dài</span>"
S["06_products"] = shell("Sản phẩm & cảnh báo", f"""
<div class="card" style="margin-bottom:12px;display:flex;gap:10px;align-items:center"><span class="inp" style="width:260px">🔍 Tìm mã sản phẩm…</span><span class="inp">Mức rủi ro: Tất cả ▾</span><span class="inp">Sắp xếp: Mức rủi ro ↓ (cùng mức: giảm điểm mạnh nhất trước)</span>
<span class="sp" style="flex:1"></span><span class="muted">Tính đến 2012-09 · 3 tháng gần nhất so với 3 tháng trước · ≥ 10 đánh giá mỗi kỳ</span></div>
<div class="card" style="margin-bottom:12px"><h4>Quy tắc có báo đúng không? – kiểm tra ngược (gắn mức tại 03/2012 và 06/2012, xem 3 tháng tiếp theo)</h4><div style="display:flex;gap:28px">""" +
    "".join(f'<div style="flex:1"><div style="font-size:12px">{lab} · {BT[k_][0]} SP</div><div style="display:flex;gap:6px;align-items:center"><div class="bar{" r" if k_ == "high" else ""}" style="width:{int(BT[k_][1] * 700)}px"></div><b>{pct(BT[k_][1])}</b></div></div>' for k_, lab in [("high", "▲ Cao"), ("medium", "● Trung bình"), ("low", "▼ Thấp")]) +
    f"""</div><div class="muted" style="margin-top:4px">Tỷ lệ tiêu cực ở 3 tháng sau – dữ liệu quy tắc chưa nhìn thấy: nhóm Cao gấp {vn(BT['high'][1] / BT['low'][1], 1)} lần nhóm Thấp</div></div>
<div class="card"><table><tr><th>Mã SP</th><th>Số ĐG</th><th>ĐTB</th><th>ĐTB 3T</th><th>Δ 3T</th><th>Tỷ lệ TC 3T</th><th>Mức rủi ro</th><th>Lý do</th><th>Dự báo</th><th></th></tr>""" +
    "".join(f"<tr><td>{r['product_id']}</td><td>{r['n_3m'] + r['n_prev_3m']}+</td><td>–</td><td>{vn(r['avg_3m'], 2)}</td><td>{vn(r['delta'], 2)}</td><td>{pct(r['neg_rate_3m'], 0)}</td><td><span class='risk hi'>▲ Cao</span></td><td>{TAG} {r['reason']}</td><td>✓/–</td><td><u>Xem dự báo</u> · <u>Hỏi AI</u></td></tr>" for r in items) +
    f"""<tr><td>B000X1Q1G8</td><td>56+</td><td>–</td><td>1,89</td><td>+0,37</td><td>74%</td><td><span class='risk hi'>▲ Cao</span></td><td>{TAG2} tỷ lệ tiêu cực cao kéo dài 74% – điểm TB tăng +0,37 sao</td><td>✓</td><td><u>Xem dự báo</u> · <u>Hỏi AI</u></td></tr>""" +
    """<tr><td>B000…</td><td>…</td><td>…</td><td>3,95</td><td>−0,31</td><td>22%</td><td><span class='risk me'>● Trung bình</span></td><td><span class='chip' style='border-color:#e34948;color:#a61b1b;font-weight:bold'>Đang giảm điểm</span> điểm TB 3 tháng giảm 0,31 sao</td><td>–</td><td><u>Xem dự báo</u></td></tr>
<tr><td>B001…</td><td>…</td><td>…</td><td>4,62</td><td>+0,05</td><td>6%</td><td><span class='risk lo'>▼ Thấp</span></td><td></td><td>✓</td><td><u>Xem dự báo</u></td></tr>
<tr><td>B00X…</td><td>…</td><td>…</td><td>–</td><td>–</td><td>–</td><td><span class='risk' style='background:#eee;color:#555'>Chưa đủ dữ liệu</span></td><td>&lt; 10 đánh giá/kỳ</td><td>–</td><td></td></tr></table>
<div class="pg" style="margin-top:10px;display:flex;justify-content:space-between"><span class="muted">Hiển thị 1–20 / """ + vn(rk["active_products_3m"]) + """ sản phẩm có đánh giá trong 3 tháng gần nhất</span><span>‹ 1 2 3 … ›</span></div></div>""",
    ann(1, 6, 104) + ann(2, 6, 160) + ann(3, 1070, 160) + ann(4, 6, 420) + ann(5, 980, 420))

tp = tr["topics"]
S["07_topics"] = shell("Chủ đề phàn nàn", f"""
<div class="row"><div class="card" style="width:430px"><h4>Chủ đề (NMF, k = {tr['k_chosen']}) – tỷ trọng trong {vn(tr['n_docs'])} đánh giá 1–2 sao</h4>""" +
    "".join(f'<div style="margin:5px 0;{"font-weight:bold" if t["topic_id"] == 2 else ""}"><div style="font-size:12px">{t["name"]}</div><div style="display:flex;gap:6px;align-items:center"><div class="bar r" style="width:{int(t["share"] * 1100)}px"></div><span class="muted">{pct(t["share"])}</span></div></div>' for t in sorted(tp, key=lambda t: -t["share"])) +
    f"""</div><div class="col card"><h4>{tp[2]['name']}</h4><div>""" + "".join(f'<span class="chip">{w}</span>' for w in tp[2]["keywords"]) + """</div>
<h4 style="margin-top:10px">Đánh giá mẫu</h4>""" + "".join(f'<div class="card" style="margin:4px 0;padding:6px 8px"><b>★ 1–2 · Id {i}</b> – {s}</div>' for i, s in zip(tp[2]["sample_review_ids"], tp[2]["sample_summaries"])) + """
<h4 style="margin-top:10px">Tỷ trọng theo năm</h4><div class="ph" style="height:110px">Đường xu hướng 2008–2012 của chủ đề đang chọn</div>
<div style="margin-top:8px"><span class="btn">Hỏi trợ lý AI về chủ đề này</span></div></div></div>""",
    ann(1, 6, 104) + ann(2, 462, 104) + ann(3, 462, 196) + ann(4, 462, 380) + ann(5, 462, 500))

fh = fr["holdout"]; best = fh[0]; nv = [x for x in fh if x["model"].startswith("Naive")][0]
S["08_forecast"] = shell("Dự báo", f"""
<div class="card" style="margin-bottom:12px;display:flex;gap:10px;align-items:center"><b>Phạm vi</b><span class="inp">◉ Toàn bộ ○ Một sản phẩm</span><span class="inp" style="width:180px">Mã sản phẩm…</span>
<b>Số tháng</b><span class="btn">3</span><span class="btn">6</span><span class="btn p">12</span></div>
<div class="row"><div class="col card"><h4>Chỉ số hài lòng theo tháng và dự báo 12 tháng (2012-10 → 2013-09)</h4><div class="ph" style="height:290px">Đường lịch sử (xám đậm) · đường dự báo (xanh) · dải khoảng tin cậy 95%<br>Trục tung: chỉ số 0–100 · Tooltip: tháng, giá trị, cận dưới–trên</div></div>
<div class="card" style="width:300px"><h4>Thông tin mô hình</h4><table><tr><td>Mô hình</td><td>ETS(A,Ad,N) – Holt giảm chấn</td></tr><tr><td>Chuỗi</td><td>01/2007–09/2012 (69 tháng)</td></tr>
<tr><td>MAE 12 tháng kiểm tra</td><td><b>{vn(best['mae_index'], 2)}</b> điểm</td></tr><tr><td>MAE mô hình ngây thơ</td><td>{vn(nv['mae_index'], 2)} điểm</td></tr><tr><td>Dự báo 09/2013</td><td>{vn(fr['forecast_12m']['2013-09']['sat_index'], 1)} ({vn(fr['forecast_12m']['2013-09']['sat_lo'], 1)}–{vn(fr['forecast_12m']['2013-09']['sat_hi'], 1)})</td></tr></table>
<div class="card" style="margin-top:10px;background:#fff8e6;border-color:#eda100"><b>Sản phẩm chưa đủ dữ liệu</b><br><span class="muted">Không đủ dữ liệu để dự báo (cần ≥ 36 tháng có đánh giá). Hiển thị xu hướng lịch sử.</span></div></div></div>""",
    ann(1, 6, 104) + ann(2, 6, 160) + ann(3, 800, 160) + ann(4, 800, 372))

S["09_ai"] = shell("Trợ lý AI", """
<div class="card" style="margin-bottom:12px;display:flex;gap:10px;align-items:center"><b>Phân tích</b><span class="inp">○ Sản phẩm ◉ Chủ đề</span><span class="inp" style="width:280px">Hàng cũ, hết hạn, bao bì hỏng khi nhận ▾</span>
<span class="btn p">Phân tích nguyên nhân</span><span class="btn">↻ Làm mới</span><span class="muted">Kết quả đã lưu đệm lúc 31/10/2026 09:00 · gemini-flash</span></div>
<div class="row"><div class="col card"><h4>Nguyên nhân khách không hài lòng</h4>
<div class="card" style="margin:4px 0"><span class="risk hi">Mức độ: cao</span> <b>[Nguyên nhân 1 – do Gemini sinh]</b><div class="muted">Mô tả ngắn … · Bằng chứng: <u>#id</u> <u>#id</u> <u>#id</u> (bấm để xem nguyên văn)</div></div>
<div class="card" style="margin:4px 0"><span class="risk me">Mức độ: trung bình</span> <b>[Nguyên nhân 2]</b><div class="muted">Mô tả ngắn … · Bằng chứng: <u>#id</u> <u>#id</u></div></div>
<div class="card" style="margin:4px 0"><span class="risk lo">Mức độ: thấp</span> <b>[Nguyên nhân 3]</b><div class="muted">Mô tả ngắn … · Bằng chứng: <u>#id</u></div></div></div>
<div class="col card"><h4>Giải pháp đề xuất</h4><table><tr><th>Nguyên nhân</th><th>Hành động</th><th>Ưu tiên</th><th>Chỉ số theo dõi</th></tr><tr><td>1</td><td>…</td><td>cao</td><td>Tỷ lệ đánh giá nhắc tới bao bì</td></tr><tr><td>2</td><td>…</td><td>trung bình</td><td>…</td></tr><tr><td>3</td><td>…</td><td>thấp</td><td>…</td></tr></table></div></div>
<div class="card" style="background:#f3f3f3"><span class="muted">ⓘ Nội dung do AI tạo từ ≤ 30 đánh giá tiêu biểu (đã bỏ UserId, ProfileName). Mọi nguyên nhân đều có ID bằng chứng đã được hệ thống kiểm tra tồn tại; 0 nguyên nhân bị loại. Khi Gemini lỗi, hiển thị kết quả đã lưu gần nhất.</span></div>""",
    ann(1, 6, 104) + ann(2, 1070, 104) + ann(3, 6, 160) + ann(4, 560, 160) + ann(5, 6, 470))

S["10_report"] = shell("Báo cáo", """
<div class="row"><div class="col card"><h4>Nội dung báo cáo PDF</h4>""" + "".join(f'<div class="step">☑ {x}</div>' for x in ["Thông tin dữ liệu và chất lượng", "7 KPI và biểu đồ tổng quan", "Kết quả so sánh mô hình", "Danh sách sản phẩm rủi ro cao", "Chủ đề phàn nàn", "Dự báo chỉ số hài lòng", "Đề xuất của trợ lý AI (nếu có)"]) + """
<div style="margin-top:10px"><span class="btn p">⬇ Tải báo cáo PDF</span></div></div>
<div class="col card"><h4>Xuất dữ liệu CSV</h4>""" + "".join(f'<div class="step"><span class="btn">⬇ {x}</span></div>' for x in ["Sản phẩm rủi ro (product_risk.csv)", "Chủ đề (topics.csv)", "Dự đoán tập kiểm tra (predictions.csv)", "Chuỗi theo tháng (monthly.csv)", "Dự báo chỉ số hài lòng (forecast.csv)", "Chỉ số mô hình (model_metrics.csv)"]) + """
<h4 style="margin-top:16px">Đổi file</h4><div class="muted">Xóa dữ liệu phiên hiện tại (dữ liệu sạch, mô hình, kết quả AI đã lưu) và quay về Trang tải dữ liệu.</div><div style="margin-top:6px"><span class="btn" style="border-color:#e34948;color:#a61b1b">Đổi file…</span> <span class="muted">(có hộp xác nhận)</span></div></div>
<div class="card" style="width:330px;height:330px;align-self:flex-end"><h4>💬 Hỏi đáp dữ liệu</h4><div class="card" style="padding:6px;margin:4px 0;background:#eef4fd">Sản phẩm nào bị phàn nàn về giao hàng nhiều nhất?</div>
<div class="card" style="padding:6px;margin:4px 0">[Trả lời của Gemini dựa trên số liệu backend gửi kèm: product_risk, topics]</div><div class="inp" style="margin-top:110px">Nhập câu hỏi…</div></div></div>""",
    ann(1, 6, 104) + ann(2, 380, 104) + ann(3, 380, 270) + ann(4, 760, 238), fab=True)

# Vị trí ký hiệu ①②…: neo vào phần tử (selector, chỉ số) – tính bằng JS theo vị trí thật của phần tử
C = ".body .card"
MARKS = {
    "01_upload": [(".body .ph", 0), (".body .btn", 0), (C, 1), (C, 2), (C, 3), (C, 4)],
    "02_overview": [(C, 0), (C, 7), (C, 8), (C, 9), (C, 10)],
    "03_eda": [(C, 0), (C, 1), (C, 2), (C, 3), (C, 4)],
    "04_model": [(C, 0), (C, 1), (C, 2), (C, 3), (C, 4), (C, 5)],
    "05_predict": [(C, 0), (C, 1), (".bar", 0), (".tok", 0), (C, 2), (C, 3)],
    "06_products": [(C, 0), (".body table", 0), (".body th", 8, "r"), (".pg", 0), (".body th", 9, "r"), (".body td .chip", 0), (C, 1)],
    "07_topics": [(C, 0), (".chip", 0), (C, 2), (".body .ph", 0), (".body .btn", 0)],
    "08_forecast": [(C, 0), (C, 1), (C, 2), (C, 3)],
    "09_ai": [(C, 0), (".body .card .muted", 0), (C, 1), (C, 5), (C, 6)],
    "10_report": [(C, 0), (C, 1), (".body .btn", 7), (C, 2)],
}
import re as _re
JS = """<script>const M=%s;const f=document.querySelector('.frame');const fr=f.getBoundingClientRect();
M.forEach(([sel,i,side],k)=>{const el=document.querySelectorAll(sel)[i];if(!el)return;const r=el.getBoundingClientRect();
const d=document.createElement('div');d.className='ann';d.textContent=k+1;d.style.left=Math.max(2,(side==='r'?r.right:r.left)-fr.left-12)+'px';
d.style.top=Math.max(2,r.top-fr.top-12)+'px';f.appendChild(d);});</script>"""
for name, html in S.items():
    html = _re.sub(r'<div class="ann"[^>]*>\d+</div>', '', html)
    html = _re.sub(r'(<div class="ph"[^>]*>)(.*?)(</div>)', r'\1<div>\2</div>\3', html, flags=_re.S)
    (OUT / f"wf_{name}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{html}' + JS % json.dumps(MARKS[name]) + '</body></html>', encoding="utf-8")
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1140, "height": 800}, device_scale_factor=2)
    for name in S:
        pg.goto((OUT / f"wf_{name}.html").as_uri()); pg.locator(".frame").screenshot(path=str(OUT / f"wf_{name}.png"))
    b.close()
print("Đã sinh", len(S), "wireframe")
