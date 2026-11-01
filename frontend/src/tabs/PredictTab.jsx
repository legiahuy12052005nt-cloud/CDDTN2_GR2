import { useState } from 'react'
import { Bot, History, Lightbulb, Loader2, Trash2, Wand2 } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, SENT, nf, pct, sessionStore as store, starColor } from '../lib/format.js'
import { Card, ErrorBox, Note, SentBadge, Stars } from '../components/ui.jsx'

const EXAMPLES = [
  ['Hàng cũ, hộp móp', 'Stale and crushed', 'The coffee arrived stale and the box was completely crushed. Very disappointed, I will not buy this again.'],
  ['Khen hương vị', 'Our new favorite snack', 'Absolutely delicious! My kids love these crackers, they taste fresh and are not too salty. Great value for the price.'],
  ['Trung tính', 'It is okay', 'The flavor is okay but a bit bland for my taste. Not bad, not great. Might try a different flavor next time.'],
  ['Thú cưng bị bệnh', 'Made my dog sick', 'My dog got sick after eating these treats. I checked the bag and they are made in China. Never again.'],
  ['Giá cao', 'Too expensive', 'Way too expensive compared to my local grocery store, and the shipping cost more than the product itself.'],
  ['Đánh giá tiếng Việt', '', 'Cà phê bị cũ, vị đắng khét và hộp giao tới bị móp méo, rất thất vọng.'],
]
const HKEY = 'fri_predict_history'

export default function PredictTab() {
  const app = useApp()
  const [summary, setSummary] = useState('')
  const [text, setText] = useState('')
  const [pid, setPid] = useState('')            // mã sản phẩm (tùy chọn – bảng 5.48 ①): gắn vào lịch sử, mở chi tiết sản phẩm
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [hist, setHist] = useState(() => store.get(HKEY, []))

  const run = async (t = text, s = summary, p = pid) => {
    setErr(null); setBusy(true)
    const productId = (p || '').trim().toUpperCase() || undefined
    try {
      const r = await api.predict({ text: t, summary: s || undefined, product_id: productId })
      setRes({ ...r, text: t, summary: s, product_id: productId })
      const h = [{ text: t, summary: s, product_id: productId, star: r.pred_star, sentiment: r.sentiment, sat: r.satisfaction_index, at: Date.now() }, ...hist.filter((x) => x.text !== t)].slice(0, 12)
      setHist(h); store.set(HKEY, h)
    } catch (e) { setErr(errorMessage(e)); setRes(null) } finally { setBusy(false) }
  }
  const words = text.trim() ? text.trim().split(/\s+/).length : 0

  return (
    <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] gap-5 items-start">
      <div className="space-y-5">
        <Card title="Nhập một đánh giá" subtitle="Mô hình học từ đánh giá tiếng Anh đã làm sạch, chuẩn hóa; văn bản nhập vào được chuẩn hóa theo cùng cách trước khi dự đoán">
          <div className="grid sm:grid-cols-[minmax(0,1fr)_12rem] gap-3">
            <label className="block text-[12px] text-muted">Tiêu đề (tùy chọn)
              <input className="input w-full mt-1" value={summary} maxLength={300} onChange={(e) => setSummary(e.target.value)} placeholder="VD: Stale coffee" /></label>
            <label className="block text-[12px] text-muted">Mã sản phẩm (tùy chọn)
              <input className="input w-full mt-1 font-mono" value={pid} maxLength={20} onChange={(e) => setPid(e.target.value.toUpperCase())} placeholder="VD: B007JFMH8M" /></label>
          </div>
          <label className="block text-[12px] text-muted mb-1 mt-3">Nội dung đánh giá</label>
          <textarea className="w-full min-h-[150px] rounded-lg border border-line px-3 py-2 text-[14px] leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/30"
            value={text} maxLength={5000} onChange={(e) => setText(e.target.value)} placeholder="VD: The coffee arrived stale and the box was crushed…"
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && words >= 3) run() }} />
          <div className="flex items-center gap-3 mt-2">
            <span className={`text-[12px] ${words && words < 3 ? 'text-neg' : 'text-muted'}`}>{words} từ{words && words < 3 ? ' – cần tối thiểu 3 từ' : ''}</span>
            <span className="flex-1" />
            <button className="btn" onClick={() => { setText(''); setSummary(''); setPid(''); setRes(null) }}>Đặt lại</button>
            <button className="btn btn-primary" disabled={busy || words < 3} onClick={() => run()}>{busy ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}Dự đoán</button>
          </div>
          <div className="mt-4 text-[12px] text-muted">Thử nhanh</div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {EXAMPLES.map(([l, s, t]) => <button key={l} className="chip" onClick={() => { setSummary(s); setText(t); run(t, s) }}>{l}</button>)}
          </div>
          {err && <div className="mt-3"><ErrorBox error={err} /></div>}
        </Card>
        {hist.length > 0 && (
          <Card title="Lịch sử dự đoán" subtitle="Trong phiên làm việc này (đóng tab trình duyệt là xóa)" action={<button className="btn btn-ghost px-2" title="Xóa lịch sử" onClick={() => { setHist([]); store.set(HKEY, []) }}><Trash2 size={15} /></button>}>
            <div className="divide-y divide-slate-100">
              {hist.map((h) => (
                <button key={h.at} className="w-full text-left py-2 flex items-center gap-3 hover:bg-slate-50 rounded" onClick={() => { setText(h.text); setSummary(h.summary || ''); setPid(h.product_id || ''); run(h.text, h.summary, h.product_id) }}>
                  <History size={14} className="text-slate-400 shrink-0" />
                  <span className="flex-1 truncate text-[13px]">{h.product_id ? <span className="font-mono text-muted">{h.product_id} · </span> : null}{h.summary ? <b className="text-ink">{h.summary} · </b> : null}{h.text}</span>
                  <span className="text-[12.5px] tabular-nums font-medium" style={{ color: starColor(h.star) }}>{h.star}★</span>
                </button>
              ))}
            </div>
          </Card>
        )}
      </div>

      <div className="space-y-5">
        {!res && !busy && (
          <Card>
            <div className="py-10 text-center text-muted">
              <Wand2 size={30} className="mx-auto text-slate-300" />
              <div className="mt-2 text-[14px] text-ink font-medium">Kết quả dự đoán hiện ở đây</div>
              <p className="text-[13px] mt-1 max-w-sm mx-auto">Số sao dự đoán, xác suất từng mức sao, chỉ số hài lòng, các từ khiến mô hình quyết định và chủ đề phàn nàn nếu đánh giá tiêu cực.</p>
            </div>
          </Card>
        )}
        {res && <Result r={res} app={app} />}
      </div>
    </div>
  )
}

function Result({ r, app }) {
  const s = SENT[r.sentiment]
  const tokMap = Object.fromEntries(r.tokens.map((t) => [t.token, t.weight]))
  const maxP = Math.max(...Object.values(r.proba))
  const maxW = Math.max(...r.tokens.map((t) => Math.abs(t.weight)), 0.01)
  return (
    <>
      <Card>
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <div className="text-[12px] text-muted">Số sao dự đoán</div>
            <div className="flex items-center gap-3 mt-1"><span className="text-[44px] leading-none font-semibold tabular-nums" style={{ color: starColor(r.pred_star) }}>{r.pred_star}</span><Stars value={r.pred_star} size={20} /></div>
          </div>
          <div>
            <div className="text-[12px] text-muted">Cảm xúc</div>
            <div className="mt-2"><SentBadge s={r.sentiment}>{s.label} · {pct(r.sentiment_proba[r.sentiment], 0)}</SentBadge></div>
          </div>
          <div className="flex-1 min-w-[180px]">
            <div className="flex justify-between text-[12px] text-muted"><span>Chỉ số hài lòng</span><span className="tabular-nums text-ink font-semibold text-[14px]">{nf(r.satisfaction_index, 1)}/100</span></div>
            <div className="mt-2 h-2.5 rounded-full relative" style={{ background: `linear-gradient(90deg, ${COLOR.neg}, #d9dde2 50%, ${COLOR.pos})` }}>
              <span className="absolute -top-1 w-1.5 h-4.5 rounded bg-ink" style={{ left: `calc(${r.satisfaction_index}% - 3px)`, height: 18 }} />
            </div>
            <div className="flex justify-between text-[11px] text-muted mt-1"><span>0</span><span>50</span><span>100</span></div>
          </div>
        </div>
        {r.note && <div className="mt-4"><Note tone="warn">{r.note}</Note></div>}
        <div className="mt-5 grid sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-6">
          <div>
            <div className="text-[12px] text-muted mb-2">Xác suất từng mức sao</div>
            {['5', '4', '3', '2', '1'].map((k) => (
              <div key={k} className="flex items-center gap-2 text-[12.5px] py-0.5">
                <span className="w-7 text-muted">{k}★</span>
                <span className="flex-1 h-3 rounded bg-slate-100"><span className="block h-3 rounded" style={{ width: `${r.proba[k] * 100}%`, background: starColor(Number(k)), opacity: r.proba[k] === maxP ? 1 : 0.55 }} /></span>
                <span className="w-12 text-right tabular-nums">{pct(r.proba[k])}</span>
              </div>
            ))}
            <div className="text-[11.5px] text-muted mt-2">Gộp: tiêu cực {pct(r.sentiment_proba.neg)} · trung tính {pct(r.sentiment_proba.neu)} · tích cực {pct(r.sentiment_proba.pos)}</div>
          </div>
          <div>
            <div className="text-[12px] text-muted mb-2">Từ ảnh hưởng nhiều nhất (TF-IDF × trọng số)</div>
            <div className="space-y-1">
              {r.tokens.slice(0, 9).map((t) => (
                <div key={t.token} className="flex items-center gap-2 text-[12.5px]">
                  <span className="w-28 truncate text-right text-ink">{t.token}</span>
                  <span className="flex-1 flex h-3"><span className="w-1/2 flex justify-end">{t.weight < 0 && <span className="h-3 rounded-l" style={{ width: `${(-t.weight / maxW) * 100}%`, background: COLOR.neg }} />}</span>
                    <span className="w-px bg-slate-300" /><span className="w-1/2">{t.weight > 0 && <span className="block h-3 rounded-r" style={{ width: `${(t.weight / maxW) * 100}%`, background: COLOR.pos }} />}</span></span>
                  <span className="w-11 text-right tabular-nums text-muted">{t.weight > 0 ? '+' : ''}{nf(t.weight, 2)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Đánh giá được tô màu theo từ ảnh hưởng" subtitle="Đỏ: kéo số sao xuống · xanh: kéo số sao lên">
        <p className="text-[14px] leading-8">
          {r.summary && <><b className="text-ink">{highlight(r.summary, tokMap, maxW)}</b><span className="text-muted"> — </span></>}
          {highlight(r.text, tokMap, maxW)}
        </p>
      </Card>

      {r.topic && (
        <Card title="Chủ đề phàn nàn gần nhất" subtitle="Mô hình NMF học trên đánh giá 1–2 sao của bộ dữ liệu">
          <div className="flex items-center gap-3">
            <span className="text-[15px] font-semibold text-ink flex-1">{r.topic.name}</span>
            <span className="text-[12.5px] text-muted">mức khớp {pct(r.topic.weight, 0)}</span>
            <button className="btn" onClick={() => app.goTab('topics', { topic: r.topic.topic_id })}>Xem chủ đề</button>
          </div>
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-emerald-50/70 border border-emerald-100 px-3 py-2.5 text-[13px]"><Lightbulb size={16} className="text-emerald-700 mt-0.5 shrink-0" /><span><b className="text-ink">Gợi ý hành động:</b> {r.suggestion}</span></div>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[12px] text-muted">
        <span>Mô hình {r.model_info?.model} · F1-macro {nf(r.model_info?.f1_macro3, 3)} · học từ {nf(r.model_info?.n_train)} đánh giá đã làm sạch · dữ liệu {r.model_info?.dataset_version} · {nf(r.latency_ms, 0)} ms · {pct(r.known_token_ratio, 0)} từ có trong từ điển mô hình</span>
        {r.product_id && <button className="btn ml-auto font-mono" onClick={() => app.openProduct(r.product_id)}>Xem sản phẩm {r.product_id}</button>}
        <button className={`btn ${r.product_id ? '' : 'ml-auto'}`} onClick={() => app.openChat(`Giải thích vì sao đánh giá sau được dự đoán ${r.pred_star} sao và người bán nên phản hồi thế nào: "${r.text.slice(0, 400)}"`)}><Bot size={15} />Hỏi trợ lý AI</button>
      </div>
    </>
  )
}

// Tô màu từ đơn có trong danh sách token ảnh hưởng; cụm 2 từ chỉ tô khi trọng số đủ lớn (≥ 40% trọng số lớn nhất)
function highlight(text, tokMap, maxW) {
  const parts = text.split(/(\s+)/)
  const norm = (w) => w.toLowerCase().replace(/n't$/, '').replace(/[^a-z0-9']/g, '')
  const words = parts.map((p) => (/^\s+$/.test(p) || !p ? null : norm(p)))
  const idx = words.map((w, i) => (w ? i : -1)).filter((i) => i >= 0)
  const weight = new Map()
  idx.forEach((i, k) => {
    const w = words[i]
    if (tokMap[w] != null) weight.set(i, tokMap[w])
    if (/n't$/i.test(parts[i]) && tokMap.not != null && !weight.has(i)) weight.set(i, tokMap.not)
    const j = idx[k + 1]
    const bw = j != null ? tokMap[`${w} ${words[j]}`] : undefined
    if (bw != null && Math.abs(bw) >= 0.4 * maxW) { if (!weight.has(i)) weight.set(i, bw); if (!weight.has(j)) weight.set(j, bw) }
  })
  return parts.map((p, i) => {
    const w = weight.get(i)
    if (w == null) return p
    const a = Math.min(1, Math.abs(w) / maxW)
    const bg = w < 0 ? `rgba(214,69,69,${0.12 + a * 0.45})` : `rgba(42,120,214,${0.12 + a * 0.45})`
    return <mark key={i} title={`${w > 0 ? '+' : ''}${nf(w, 2)}`} className="rounded px-0.5 text-ink" style={{ background: bg }}>{p}</mark>
  })
}
