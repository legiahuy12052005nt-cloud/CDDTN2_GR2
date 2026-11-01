import { useMemo, useState } from 'react'
import { Bar as RBar, BarChart, CartesianGrid, Cell, ComposedChart, Line, LineChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Filter, RotateCcw, SearchX, X } from 'lucide-react'
import { api } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, SENT, monthLabel, monthShort, nf, pct, sentOfStar, starColor } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Card, ChartTip, Empty, ErrorBox, Loading, Select, Stat, axisProps } from '../components/ui.jsx'

const EMPTY = { date_from: '', date_to: '', score: '', sentiment: '', product_id: '' }
const MIN_PER_MONTH = 30           // điểm TB/tỷ lệ tiêu cực của tháng < 30 đánh giá dao động quá mạnh
const norm = (d) => ({ ...d, product_id: (d.product_id || '').trim().toUpperCase() })

// Lỗi của bộ lọc đang soạn – chặn bấm Áp dụng thay vì gửi đi rồi nhận về 0 đánh giá
function draftErrors(d) {
  const e = {}
  if (d.date_from && d.date_to && d.date_from > d.date_to) e.date = '“Từ tháng” phải trước hoặc trùng “Đến tháng”.'
  if (d.score && d.sentiment && sentOfStar(Number(d.score)) !== d.sentiment) e.sent = `${d.score} sao không thuộc nhóm ${SENT[d.sentiment].label} (${SENT[d.sentiment].range}).`
  return e
}

// Chuỗi tháng liên tục (tháng không có đánh giá → n = 0) để trục thời gian không bị “co” khi dữ liệu lọc thưa
function fillMonths(rows) {
  if (!rows.length) return []
  const by = Object.fromEntries(rows.map((r) => [r.month, r]))
  const [y0, m0] = rows[0].month.split('-').map(Number); const [y1, m1] = rows[rows.length - 1].month.split('-').map(Number)
  const out = []
  for (let t = y0 * 12 + m0 - 1; t <= y1 * 12 + m1 - 1; t++) {
    const m = `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
    out.push(by[m] || { month: m, n: 0, avg_score: null, neg_rate: null })
  }
  return out
}

export default function EdaTab() {
  const app = useApp()
  const [draft, setDraft] = useState(EMPTY)
  const [f, setF] = useState(EMPTY)
  const key = JSON.stringify(f)
  const all = useApi(() => api.eda('monthly'), [])
  const months = useMemo(() => (all.data?.data || []).map((d) => d.month), [all.data])
  const kpi = useApi(() => api.kpi(f), [key])
  const dist = useApi(() => api.eda('score_dist', f), [key])
  const mon = useApi(() => api.eda('monthly', f), [key])
  const len = useApi(() => api.eda('length_by_score', f), [key])
  const kw = useApi(() => api.eda('keywords', f), [key])
  const top = useApi(() => api.eda('top_products', f), [key])
  // thông tin sản phẩm đang lọc: có trong dữ liệu không, có đánh giá trong khoảng nào – để giải thích khi kết quả rỗng
  const prod = useApi(() => (f.product_id ? api.products({ q: f.product_id, page_size: 5 }).then((r) => r.items.find((x) => x.product_id === f.product_id) || null) : Promise.resolve(null)), [f.product_id])

  const active = Object.values(f).some(Boolean)
  const dirty = JSON.stringify(norm(draft)) !== JSON.stringify(norm(f))
  const errs = draftErrors(draft)
  const hasErr = Object.keys(errs).length > 0
  const apply = () => { if (hasErr) return; const d = norm(draft); setDraft(d); setF(d) }
  const reset = () => { setDraft(EMPTY); setF(EMPTY) }
  // bỏ một điều kiện ngay từ dòng “Đang hiển thị” (áp dụng luôn, không cần bấm Áp dụng)
  const removeTag = (k) => {
    const keys = k === 'date' ? ['date_from', 'date_to'] : [k]
    const clear = (o) => ({ ...o, ...Object.fromEntries(keys.map((x) => [x, ''])) })
    setDraft(clear); setF(clear)
  }
  const setD = (k, v) => setDraft((d) => {
    const n = { ...d, [k]: v }
    // số sao và cảm xúc ràng buộc nhau: chọn cái này thì bỏ cái kia nếu mâu thuẫn
    if (k === 'score' && v && n.sentiment && sentOfStar(Number(v)) !== n.sentiment) n.sentiment = ''
    if (k === 'sentiment' && v && n.score && sentOfStar(Number(n.score)) !== v) n.score = ''
    return n
  })

  const fromOpts = [['', 'Tất cả'], ...months.map((m) => [m, monthLabel(m), !!draft.date_to && m > draft.date_to])]
  const toOpts = [['', 'Tất cả'], ...months.map((m) => [m, monthLabel(m), !!draft.date_from && m < draft.date_from])]
  const scoreOpts = [['', 'Tất cả'], ...[1, 2, 3, 4, 5].map((s) => [String(s), `${s} sao`, !!draft.sentiment && sentOfStar(s) !== draft.sentiment])]
  const sentOpts = [['', 'Tất cả'], ...Object.entries(SENT).map(([k, v]) => [k, `${v.label} (${v.range})`, !!draft.score && sentOfStar(Number(draft.score)) !== k])]

  const n = kpi.data?.n_reviews
  const none = !kpi.loading && !kpi.error && n === 0
  const monData = fillMonths(mon.data?.data || [])
  // toàn bộ dữ liệu: bỏ các tháng đầu (1999–2006) rất thưa; khi đã lọc thì giữ trọn khoảng thời gian của kết quả lọc
  // (trước đây luôn cắt từ tháng đầu tiên có ≥ 30 đánh giá nên lọc một sản phẩm bị mất phần lớn lịch sử)
  const firstBig = active ? -1 : monData.findIndex((d) => d.n >= MIN_PER_MONTH)
  const monTrim = firstBig > 0 ? monData.slice(firstBig) : monData
  const nBig = monTrim.filter((d) => d.n >= MIN_PER_MONTH).length
  const T = nBig >= 3 || !monTrim.length ? MIN_PER_MONTH : 1     // bộ lọc còn quá ít dữ liệu: vẽ mọi tháng có đánh giá, kèm cảnh báo
  const lineData = monTrim.map((d) => (d.n >= T ? d : { ...d, avg_score: null, neg_rate: null }))
  const distData = dist.data?.data || []
  const distTotal = distData.reduce((a, b) => a + b.n, 0)
  const tags = [
    f.date_from || f.date_to ? ['date', `Tháng: ${f.date_from ? monthLabel(f.date_from) : 'đầu'} – ${f.date_to ? monthLabel(f.date_to) : 'cuối'}`] : null,
    f.score ? ['score', `${f.score} sao`] : null,
    f.sentiment ? ['sentiment', `${SENT[f.sentiment].label} (${SENT[f.sentiment].range})`] : null,
    f.product_id ? ['product_id', `Sản phẩm ${f.product_id}`] : null,
  ].filter(Boolean)
  const emptyMsg = 'Không có đánh giá nào khớp bộ lọc'

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-line shadow-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-center gap-2 text-[13px] font-semibold text-ink mr-1 self-center"><Filter size={15} />Bộ lọc</div>
          <Select label="Từ tháng" value={draft.date_from} onChange={(v) => setD('date_from', v)} options={fromOpts} className="w-32" invalid={!!errs.date} />
          <Select label="Đến tháng" value={draft.date_to} onChange={(v) => setD('date_to', v)} options={toOpts} className="w-32" invalid={!!errs.date} />
          <Select label="Số sao" value={draft.score} onChange={(v) => setD('score', v)} options={scoreOpts} className="w-28" invalid={!!errs.sent} />
          <Select label="Cảm xúc" value={draft.sentiment} onChange={(v) => setD('sentiment', v)} options={sentOpts} className="w-44" invalid={!!errs.sent} />
          <label className="flex flex-col gap-1 text-[12px] text-muted">Mã sản phẩm
            <input className="input w-40 font-mono" placeholder="VD: B007JFMH8M" value={draft.product_id} onChange={(e) => setD('product_id', e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && apply()} />
          </label>
          <button className={`btn btn-primary relative ${dirty && !hasErr ? 'ring-2 ring-primary/30' : ''}`} disabled={hasErr || !dirty} onClick={apply}>
            Áp dụng{dirty && !hasErr && <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-amber-400 border-2 border-white" />}
          </button>
          {(active || Object.values(draft).some(Boolean)) && <button className="btn" onClick={reset}><RotateCcw size={14} />Bỏ lọc</button>}
          {dirty && !hasErr && <span className="self-center text-[12px] text-amber-700">Có thay đổi chưa áp dụng – bấm “Áp dụng” (hoặc Enter ở ô mã sản phẩm)</span>}
        </div>
        {hasErr && <div className="mt-2 flex items-center gap-1.5 text-[12.5px] text-red-700"><AlertTriangle size={14} />{Object.values(errs).join(' ')}</div>}
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[12.5px]">
          <span className="text-muted">Đang hiển thị:</span>
          {tags.length === 0 ? <span className="text-ink">toàn bộ dữ liệu</span> : tags.map(([k, l]) => (
            <span key={k} className="inline-flex items-center gap-1 rounded-full bg-primarySoft text-[#1c4f8f] pl-2.5 pr-1 py-0.5">{l}
              <button className="rounded-full p-0.5 hover:bg-white/70" aria-label={`Bỏ điều kiện ${l}`} onClick={() => removeTag(k)}><X size={12} /></button>
            </span>
          ))}
          {tags.length > 1 && <span className="text-muted">· các điều kiện áp dụng đồng thời</span>}
          {f.product_id && prod.data && <span className="text-muted">· {f.product_id}: {nf(prod.data.n_reviews)} đánh giá, {monthLabel(prod.data.first_month)} → {monthLabel(prod.data.last_month)}, điểm TB {nf(prod.data.avg_score, 2)}</span>}
          {f.product_id && !prod.loading && !prod.error && prod.data === null && <span className="text-red-700">· không có mã {f.product_id} trong dữ liệu đang nạp</span>}
        </div>
      </div>

      {kpi.error ? <ErrorBox error={kpi.error} /> : (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Đánh giá" value={kpi.loading ? '…' : nf(n)} />
          <Stat label="Sản phẩm" value={kpi.loading ? '…' : nf(kpi.data?.n_products)} />
          <Stat label="Điểm sao TB" value={kpi.loading ? '…' : none ? '–' : nf(kpi.data?.avg_score, 2)} />
          <Stat label="Chỉ số hài lòng" value={kpi.loading ? '…' : none ? '–' : nf(kpi.data?.satisfaction_index, 1)} />
          <Stat label="Tỷ lệ tiêu cực" value={kpi.loading ? '…' : none ? '–' : pct(kpi.data?.neg_rate)} tone={none ? undefined : COLOR.neg} />
        </div>
      )}
      {none && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-[13px] text-amber-900">
          <SearchX size={16} className="mt-0.5 shrink-0" />
          <div>
            <b>{emptyMsg}.</b>{' '}
            {f.product_id && prod.data === null && !prod.loading ? `Mã ${f.product_id} không có trong dữ liệu đang nạp – kiểm tra lại mã (10 ký tự, ví dụ B007JFMH8M).`
              : f.product_id && prod.data ? `Sản phẩm ${f.product_id} chỉ có ${nf(prod.data.n_reviews)} đánh giá từ ${monthLabel(prod.data.first_month)} đến ${monthLabel(prod.data.last_month)}; khoảng tháng, số sao hoặc cảm xúc đang chọn không trùng với các đánh giá này.`
              : 'Các điều kiện được áp dụng đồng thời – hãy nới khoảng tháng hoặc bỏ bớt điều kiện.'}
          </div>
        </div>
      )}

      <div className="grid xl:grid-cols-2 gap-5">
        <Card title="Số đánh giá theo tháng" subtitle={!active ? 'Lượng đánh giá tăng mạnh từ 2008; các tháng đầu rất ít dữ liệu' : none ? emptyMsg
          : `${nf(n)} đánh giá khớp bộ lọc, ${nf(monData.filter((d) => d.n > 0).length)} tháng có đánh giá (${monthLabel(monData[0]?.month)} – ${monthLabel(monData[monData.length - 1]?.month)})`}>
          {mon.loading ? <Loading h="h-64" /> : mon.error ? <ErrorBox error={mon.error} /> : !monTrim.length ? <Empty title={emptyMsg} /> : (
            <div className="h-64"><ResponsiveContainer>
              <BarChart data={monTrim} margin={{ top: 6, right: 8, bottom: 0, left: -6 }}>
                <CartesianGrid stroke={COLOR.grid} vertical={false} />
                <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={28} />
                <YAxis tickFormatter={(v) => nf(v)} allowDecimals={false} {...axisProps} />
                <Tooltip cursor={{ fill: '#f1f5f9' }} content={<ChartTip labelFormat={monthLabel} rows={(d) => [['Số đánh giá', nf(d.n), COLOR.primary], ['Điểm TB', nf(d.avg_score, 2)]]} />} />
                <RBar dataKey="n" fill={COLOR.primary} radius={[2, 2, 0, 0]} minPointSize={0} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Điểm sao trung bình và tỷ lệ tiêu cực theo tháng"
          subtitle={T === MIN_PER_MONTH ? `Hai chỉ số vẽ riêng trục; chỉ hiển thị tháng có ≥ ${MIN_PER_MONTH} đánh giá` : 'Bộ lọc còn ít dữ liệu: hiển thị mọi tháng có đánh giá – mỗi điểm chỉ từ vài đánh giá nên dao động mạnh'}>
          {mon.loading ? <Loading h="h-64" /> : mon.error ? <ErrorBox error={mon.error} /> : !monTrim.length ? <Empty title={emptyMsg} /> : (
            <div className="grid grid-rows-2 h-64 gap-1">
              <ResponsiveContainer>
                <LineChart data={lineData} syncId="m" margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
                  <CartesianGrid stroke={COLOR.grid} vertical={false} />
                  <XAxis dataKey="month" hide />
                  <YAxis domain={[(min) => Math.max(1, Math.floor(min * 2) / 2), 5]} tickCount={4} tickFormatter={(v) => nf(v, 1)} {...axisProps} width={44} />
                  <Tooltip content={<ChartTip labelFormat={monthLabel} rows={(d) => [['Điểm TB', nf(d.avg_score, 2), COLOR.ink], ['Tỷ lệ tiêu cực', pct(d.neg_rate), COLOR.neg], ['Số đánh giá', nf(d.n)]]} />} />
                  <Line dataKey="avg_score" stroke={COLOR.ink} strokeWidth={2} dot={T === 1 ? { r: 2.5 } : false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
              <ResponsiveContainer>
                <LineChart data={lineData} syncId="m" margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
                  <CartesianGrid stroke={COLOR.grid} vertical={false} />
                  <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={28} />
                  <YAxis domain={[0, 'auto']} tickFormatter={(v) => pct(v, 0)} {...axisProps} width={44} />
                  <Tooltip content={() => null} />
                  <Line dataKey="neg_rate" stroke={COLOR.neg} strokeWidth={2} dot={T === 1 ? { r: 2.5 } : false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="flex gap-4 text-[12px] text-muted mt-1"><Legend c={COLOR.ink} l="Điểm sao TB (trên)" /><Legend c={COLOR.neg} l="Tỷ lệ tiêu cực (dưới)" /></div>
        </Card>
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Card title="Phân bố số sao">
          {dist.loading ? <Loading h="h-60" /> : dist.error ? <ErrorBox error={dist.error} /> : distTotal === 0 ? <Empty title={emptyMsg} /> : (
            <div className="h-60"><ResponsiveContainer>
              <BarChart data={distData} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: -8 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="score" tickFormatter={(s) => `${s} sao`} {...axisProps} width={52} />
                <Tooltip cursor={{ fill: '#f1f5f9' }} content={<ChartTip labelFormat={(s) => `${s} sao`} rows={(d) => [['Số đánh giá', nf(d.n), starColor(d.score)], ['Tỷ lệ', pct(d.share)]]} />} />
                <RBar dataKey="n" radius={[0, 4, 4, 0]} barSize={22} isAnimationActive={false} label={{ position: 'right', formatter: (v) => nf(v), fontSize: 11, fill: COLOR.text }}>
                  {distData.map((d) => <Cell key={d.score} fill={starColor(d.score)} />)}
                </RBar>
              </BarChart>
            </ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Độ dài đánh giá theo số sao" subtitle="Số từ: thanh là khoảng tứ phân vị Q1–Q3, chấm là trung vị">
          {len.loading ? <Loading h="h-60" /> : len.error ? <ErrorBox error={len.error} /> : !(len.data?.data || []).length ? <Empty title={emptyMsg} /> : (
            <div className="h-60"><ResponsiveContainer>
              <ComposedChart data={(len.data?.data || []).map((d) => ({ ...d, iqr: [d.q1, d.q3] }))} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
                <CartesianGrid stroke={COLOR.grid} vertical={false} />
                <XAxis dataKey="score" tickFormatter={(s) => `${s} sao`} {...axisProps} />
                <YAxis {...axisProps} />
                <Tooltip cursor={{ fill: '#f1f5f9' }} content={<ChartTip labelFormat={(s) => `${s} sao`} rows={(d) => [['Trung vị', `${nf(d.median)} từ`, starColor(d.score)], ['Q1 – Q3', `${nf(d.q1)} – ${nf(d.q3)}`], ['Trung bình', nf(d.mean, 1)], ['Số đánh giá', nf(d.n)]]} />} />
                <RBar dataKey="iqr" barSize={28} radius={4} isAnimationActive={false}>
                  {(len.data?.data || []).map((d) => <Cell key={d.score} fill={starColor(d.score)} fillOpacity={0.35} />)}
                </RBar>
                <Scatter dataKey="median" fill={COLOR.ink} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer></div>
          )}
        </Card>
        <Card title="Sản phẩm nhiều đánh giá nhất" subtitle={active ? 'Trong các đánh giá khớp bộ lọc' : undefined} pad={false}>
          {top.loading ? <Loading h="h-60" /> : top.error ? <div className="p-5"><ErrorBox error={top.error} /></div> : !(top.data?.data || []).length ? <Empty title={emptyMsg} /> : (
            <table className="tbl">
              <thead><tr><th>Sản phẩm</th><th className="text-right">Đánh giá</th><th className="text-right">Điểm TB</th><th className="text-right">Tiêu cực</th></tr></thead>
              <tbody>{(top.data?.data || []).map((p) => (
                <tr key={p.product_id} className="clickable" onClick={() => app.openProduct(p.product_id)}>
                  <td className="font-mono text-[12.5px] text-ink">{p.product_id}</td><td className="text-right">{nf(p.n)}</td>
                  <td className="text-right">{nf(p.avg_score, 2)}</td><td className="text-right">{pct(p.neg_rate)}</td>
                </tr>))}</tbody>
            </table>
          )}
        </Card>
      </div>

      <Card title="Từ và cụm từ đặc trưng theo cảm xúc" subtitle="Log-odds có prior Dirichlet (Monroe và cộng sự, 2008): điểm z càng cao, từ càng đặc trưng cho nhóm; đã bỏ từ dừng nhưng giữ “not, no, never, too, very”">
        {kw.loading ? <Loading h="h-80" /> : kw.error ? <ErrorBox error={kw.error} /> : <KeywordPair data={kw.data?.data || []} oneGroup={!!(f.sentiment || f.score)} none={none} />}
      </Card>

      <Quality />
    </div>
  )
}

function Legend({ c, l }) { return <span className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5 rounded" style={{ background: c }} />{l}</span> }

function KeywordPair({ data, oneGroup, none }) {
  const neg = data.filter((d) => d.sentiment === 'neg'); const pos = data.filter((d) => d.sentiment === 'pos')
  const max = Math.max(...data.map((d) => d.z), 1)
  if (!data.length) return (
    <div className="text-[13px] text-muted">
      {none ? 'Không có đánh giá nào khớp bộ lọc.'
        : oneGroup ? 'Biểu đồ này so sánh nhóm Tiêu cực (1–2 sao) với nhóm Tích cực (4–5 sao) nên cần cả hai nhóm; bộ lọc số sao/cảm xúc hiện tại chỉ giữ một nhóm. Bỏ điều kiện số sao, cảm xúc để xem.'
          : 'Không đủ đánh giá để so sánh: cần ít nhất 20 đánh giá tiêu cực và 20 đánh giá tích cực trong bộ lọc.'}
    </div>
  )
  const col = (items, color, title) => (
    <div>
      <div className="text-[13px] font-medium mb-2" style={{ color }}>{title}</div>
      <div className="space-y-1">
        {items.map((d) => (
          <div key={d.term} className="flex items-center gap-2 text-[12.5px]">
            <span className="w-32 truncate text-ink text-right">{d.term}</span>
            <span className="flex-1 h-4 bg-slate-50 rounded"><span className="block h-4 rounded" style={{ width: `${(d.z / max) * 100}%`, background: color, opacity: 0.85 }} /></span>
            <span className="w-10 text-right tabular-nums text-muted">{nf(d.z, 0)}</span>
          </div>
        ))}
      </div>
    </div>
  )
  return <div className="grid md:grid-cols-2 gap-8">{col(neg, COLOR.neg, 'Đặc trưng đánh giá tiêu cực (1–2 sao)')}{col(pos, COLOR.pos, 'Đặc trưng đánh giá tích cực (4–5 sao)')}</div>
}

function Quality() {
  const q = useApi(() => api.quality(), [])
  if (q.loading) return <Card title="Chất lượng dữ liệu gốc"><Loading /></Card>
  if (q.error) return <ErrorBox error={q.error} />
  const d = q.data
  const order = ['Id', 'ProductId', 'Score', 'Time', 'Summary', 'Text', 'HelpfulnessNumerator', 'HelpfulnessDenominator', 'UserId']
  const keys = d.preview?.[0] ? Object.keys(d.preview[0]) : []
  const cols = [...order.filter((c) => keys.includes(c)), ...keys.filter((c) => !order.includes(c))]
  const short = { HelpfulnessNumerator: 'Help. tử', HelpfulnessDenominator: 'Help. mẫu' }
  const cell = (c, v) => c === 'Time' && v ? new Date(Number(v) * 1000).toISOString().slice(0, 10) : String(v ?? '')
  return (
    <Card title="Chất lượng dữ liệu gốc" subtitle={`${d.file_name} · ${nf(d.n_rows)} dòng × ${d.n_columns} cột · ${d.time_min} → ${d.time_max} · tính trên file gốc, không phụ thuộc bộ lọc`}>
      <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)] gap-5">
        <div className="space-y-3 text-[13px]">
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-muted text-[12px]">Bản ghi trùng (UserId, Time, Text)</div>
            <div className="text-[18px] font-semibold text-ink tabular-nums">{nf(d.n_duplicates)} <span className="text-[13px] font-normal text-muted">({pct(d.n_duplicates / d.n_rows)})</span></div>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <div className="text-muted text-[12px]">Helpfulness tử số &gt; mẫu số</div>
            <div className="text-[18px] font-semibold text-ink tabular-nums">{nf(d.n_helpfulness_invalid)}</div>
          </div>
          <div>
            <div className="text-muted text-[12px] mb-1">Giá trị thiếu theo cột</div>
            {Object.entries(d.missing_by_column).map(([c, v]) => (
              <div key={c} className="flex justify-between py-0.5 border-b border-slate-100"><span>{c}</span><span className="tabular-nums" style={{ color: v ? COLOR.neg : COLOR.muted }}>{nf(v)}</span></div>
            ))}
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-muted text-[12px] mb-1">20 dòng đầu của file gốc (đã bỏ ProfileName; Time hiển thị dạng ngày)</div>
          <div className="overflow-auto max-h-[420px] rounded-lg border border-line">
            <table className="tbl">
              <thead className="sticky top-0"><tr>{cols.map((c) => <th key={c}>{short[c] || c}</th>)}</tr></thead>
              <tbody>{d.preview.map((r, i) => <tr key={i}>{cols.map((c) => (
                <td key={c} className={c === 'Text' ? 'min-w-[320px] text-[12px]' : c === 'Summary' ? 'min-w-[160px] text-[12px]' : 'whitespace-nowrap text-[12px]'}>
                  {c === 'Text' ? <span className="line-clamp-2" title={r[c]}>{r[c]}</span> : cell(c, r[c])}
                </td>))}</tr>)}</tbody>
            </table>
          </div>
        </div>
      </div>
    </Card>
  )
}
