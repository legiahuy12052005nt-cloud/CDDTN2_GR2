import { useEffect, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Bot, Loader2, Sparkles, X } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, monthLabel, monthShort, nf, pct, signed } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import InsightView from './InsightView.jsx'
import { Bar, ChartTip, ErrorBox, Loading, Note, ReviewQuote, RiskBadge, SignalTag, Stars, axisProps } from './ui.jsx'

// Ngăn chi tiết sản phẩm: chỉ số, xu hướng tháng + dự báo, chủ đề phàn nàn, đánh giá mẫu, phân tích AI
export default function ProductDrawer({ productId, onClose }) {
  const app = useApp()
  const row = useApi(() => api.products({ q: productId, page_size: 5 }).then((r) => { const it = r.items.find((x) => x.product_id === productId); return it ? { ...it, as_of: r.as_of } : null }), [productId])
  const fc = useApi(() => api.forecast({ product_id: productId, months: 6 }), [productId])
  const sat = useApi(() => api.satisfaction({ product_id: productId }), [productId])
  const tp = useApi(() => api.topics(productId).catch(() => null), [productId])
  const [ai, setAi] = useState({ loading: false, data: null, error: null })
  useEffect(() => { const f = (e) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', f); return () => window.removeEventListener('keydown', f) }, [onClose])

  const runAi = async (refresh = false) => {
    setAi({ loading: true, data: ai.data, error: null })
    try { setAi({ loading: false, data: await api.aiInsights({ scope: 'product', id: productId, refresh }), error: null }) } catch (e) { setAi({ loading: false, data: null, error: errorMessage(e) }) }
  }
  const p = row.data
  const fcPts = fc.data?.eligible ? fc.data.forecast : []
  // dự báo bắt đầu sau tháng trọn vẹn cuối: bỏ tháng chưa trọn khỏi lịch sử để không vẽ trùng một tháng hai lần
  const lastFull = app.health?.dataset?.last_full_month
  const series = (sat.data?.series || []).filter((s) => !fcPts.length || !lastFull || s.month <= lastFull).slice(-36)
  const chart = [...series.map((s) => ({ month: s.month, actual: s.sat_index, n: s.n })), ...fcPts.map((f) => ({ month: f.month, fc: f.sat_index, band: [f.lo, f.hi] }))]
  const asOf = p?.as_of
  const w1 = asOf ? addMonths(asOf, -2) : null; const w0 = asOf ? addMonths(asOf, -5) : null
  const samples = (tp.data?.topics || []).flatMap((t) => t.samples.slice(0, 1).map((s) => ({ ...s, topic: t.name }))).slice(0, 4)

  return (
    <div className="fixed inset-0 z-[45] flex justify-end" role="dialog" aria-modal="true" aria-label={`Sản phẩm ${productId}`}>
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <aside className="relative w-full max-w-[640px] h-full bg-canvas overflow-y-auto shadow-2xl">
        <div className="sticky top-0 z-10 bg-white border-b border-line px-5 py-3 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-muted">Sản phẩm</div>
            <div className="font-semibold text-ink font-mono text-[16px]">{productId}</div>
          </div>
          {p && <RiskBadge level={p.risk_level} />}
          <a className="btn" href={`https://www.amazon.com/dp/${productId}`} target="_blank" rel="noreferrer">Xem trên Amazon</a>
          <button className="btn btn-ghost px-2" onClick={onClose} aria-label="Đóng"><X size={17} /></button>
        </div>
        <div className="p-5 space-y-4">
          {row.loading ? <Loading /> : row.error ? <ErrorBox error={row.error} /> : !p ? <ErrorBox error={`Không tìm thấy sản phẩm ${productId}`} /> : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <Mini label="Số đánh giá" value={nf(p.n_reviews)} sub={`${p.first_month} → ${p.last_month}`} />
                <Mini label="Điểm TB toàn kỳ" value={<span className="flex items-center gap-1.5">{nf(p.avg_score, 2)}<Stars value={p.avg_score} size={11} /></span>} />
                <Mini label="Tỷ lệ tiêu cực" value={pct(p.neg_rate)} />
                <Mini label="Tháng có đánh giá" value={nf(p.n_active_months)} sub={p.forecastable ? 'đủ điều kiện dự báo' : 'cần ≥ 36 để dự báo'} />
              </div>
              <div className="bg-white rounded-xl border border-line p-4">
                <div className="text-[13px] font-semibold text-ink">Cảnh báo tính đến {monthLabel(asOf)}</div>
                <div className="grid grid-cols-3 gap-3 mt-2 text-[13px]">
                  <div><div className="text-muted text-[12px]">3 tháng trước ({p.n_prev_3m} ĐG)</div><div className="font-semibold tabular-nums text-ink">{nf(p.avg_prev_3m, 2)} ★</div></div>
                  <div><div className="text-muted text-[12px]">3 tháng gần nhất ({p.n_3m} ĐG)</div><div className="font-semibold tabular-nums text-ink">{nf(p.avg_3m, 2)} ★</div></div>
                  <div><div className="text-muted text-[12px]">Thay đổi · tiêu cực</div><div className="font-semibold tabular-nums"><span style={{ color: p.delta == null ? COLOR.muted : p.delta <= -0.25 ? COLOR.high : p.delta > 0 ? COLOR.low : COLOR.ink }}>{signed(p.delta)}</span> · <span style={{ color: p.neg_rate_3m >= 0.25 ? COLOR.high : COLOR.ink }}>{pct(p.neg_rate_3m, 0)}</span></div></div>
                </div>
                {p.reason && <div className="mt-2 text-[12.5px]" style={{ color: p.signal === 'negative' ? COLOR.medium : COLOR.high }}><SignalTag s={p.signal} />Lý do: {p.reason}</div>}
                {p.risk_level === 'insufficient' && <div className="mt-2 text-[12.5px] text-muted">Cần ít nhất 10 đánh giá trong mỗi cửa sổ 3 tháng để đánh giá rủi ro.</div>}
              </div>
            </>
          )}

          <div className="bg-white rounded-xl border border-line p-4">
            <div className="flex items-baseline gap-2"><div className="text-[13px] font-semibold text-ink flex-1">Chỉ số hài lòng theo tháng</div><div className="text-[11.5px] text-muted">36 tháng gần nhất có đánh giá{fcPts.length ? ' + dự báo 6 tháng' : ''}</div></div>
            {sat.loading ? <Loading h="h-52" /> : chart.length === 0 ? <div className="text-[13px] text-muted py-6">Chưa có dữ liệu.</div> : (
              <div className="h-56 mt-2">
                <ResponsiveContainer>
                  <ComposedChart data={chart} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                    <CartesianGrid stroke={COLOR.grid} vertical={false} />
                    <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={24} />
                    <YAxis domain={[0, 100]} {...axisProps} />
                    {w0 && <ReferenceArea x1={w0} x2={addMonths(asOf, -3)} fill="#94a3b8" fillOpacity={0.08} />}
                    {w1 && <ReferenceArea x1={w1} x2={asOf} fill={COLOR.high} fillOpacity={0.07} />}
                    <Tooltip content={<ChartTip labelFormat={monthLabel} rows={(d) => d.actual != null ? [['Chỉ số hài lòng', nf(d.actual, 1), COLOR.ink], ['Số đánh giá', nf(d.n)]] : [['Dự báo', nf(d.fc, 1), COLOR.primary], ['Khoảng 95%', `${nf(d.band[0], 0)}–${nf(d.band[1], 0)}`]]} />} />
                    <Area dataKey="band" stroke="none" fill={COLOR.primary} fillOpacity={0.12} isAnimationActive={false} />
                    <Line dataKey="actual" stroke={COLOR.ink} strokeWidth={2} dot={{ r: 2.5 }} connectNulls={false} isAnimationActive={false} />
                    <Line dataKey="fc" stroke={COLOR.primary} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
            {fc.data && !fc.data.eligible && <div className="text-[12px] text-muted mt-1">{fc.data.message}</div>}
            {fc.data?.eligible && <div className="text-[12px] text-muted mt-1">{fc.data.model} · {fc.data.message}</div>}
          </div>

          <div className="bg-white rounded-xl border border-line p-4">
            <div className="text-[13px] font-semibold text-ink">Khách phàn nàn điều gì</div>
            {tp.loading ? <Loading h="h-24" /> : !tp.data?.topics?.length ? <div className="text-[13px] text-muted mt-1">Sản phẩm chưa có đánh giá tiêu cực được gán chủ đề.</div> : (
              <div className="mt-2 space-y-1.5">
                <div className="text-[12px] text-muted">{tp.data.n_negative} đánh giá 1–2 sao</div>
                {tp.data.topics.map((t) => (
                  <div key={t.topic_id} className="flex items-center gap-3 text-[13px]">
                    <span className="flex-1 truncate">{t.name}</span>
                    <Bar value={t.share} color={COLOR.neg} w="w-28" /><span className="w-12 text-right tabular-nums text-muted">{pct(t.share, 0)}</span>
                  </div>
                ))}
              </div>
            )}
            {samples.length > 0 && <div className="mt-3 space-y-2">{samples.map((s) => <ReviewQuote key={s.review_id} r={s} />)}</div>}
          </div>

          <div className="bg-white rounded-xl border border-line p-4">
            <div className="flex items-center gap-2">
              <div className="flex-1"><div className="text-[13px] font-semibold text-ink">Nguyên nhân và giải pháp</div><div className="text-[12px] text-muted">Trợ lý AI đọc tối đa 30 đánh giá 1–2 sao (ưu tiên 12 tháng gần nhất, nhiều lượt hữu ích); mỗi nguyên nhân có đánh giá làm bằng chứng</div></div>
              <button className="btn btn-ai" disabled={ai.loading} onClick={() => runAi(!!ai.data)}>{ai.loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}{ai.data ? 'Phân tích lại' : 'Phân tích bằng AI'}</button>
            </div>
            {ai.error && <div className="mt-3"><ErrorBox error={ai.error} /></div>}
            {ai.loading && !ai.data && <Loading h="h-24" label="Đang gửi đánh giá cho trợ lý AI…" />}
            {ai.data && <div className="mt-3"><InsightView data={ai.data} /></div>}
            <button className="btn mt-3" onClick={() => app.openChat(`Sản phẩm ${productId} đang gặp vấn đề gì và nên làm gì trước?`)}><Bot size={15} />Hỏi trợ lý về sản phẩm này</button>
          </div>
          {p?.risk_level === 'high' && !ai.data && <Note tone="ai">Sản phẩm rủi ro cao: nên chạy phân tích AI để có danh sách nguyên nhân kèm bằng chứng trước khi liên hệ nhà cung cấp.</Note>}
        </div>
      </aside>
    </div>
  )
}

function Mini({ label, value, sub }) {
  return (
    <div className="bg-white rounded-xl border border-line px-3 py-2.5">
      <div className="text-[11.5px] text-muted">{label}</div>
      <div className="text-[16px] font-semibold text-ink tabular-nums mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

function addMonths(m, k) {
  const [y, mo] = m.split('-').map(Number); const t = y * 12 + (mo - 1) + k
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
}
