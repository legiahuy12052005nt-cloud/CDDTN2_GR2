import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Bot, Lightbulb, Loader2, Sparkles } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, monthLabel, monthShort, nf, pct } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import InsightView from '../components/InsightView.jsx'
import { Card, ChartTip, ErrorBox, Loading, ReviewQuote, axisProps } from '../components/ui.jsx'

export default function TopicsTab() {
  const app = useApp()
  const t = useApi(() => api.topics(), [])
  const [sel, setSel] = useState(app.focusTopic ?? null)
  const [ai, setAi] = useState({})
  if (t.loading) return <Loading h="h-80" />
  if (t.error) return <ErrorBox error={t.error} onRetry={t.reload} />
  const topics = [...t.data.topics].sort((a, b) => b.share - a.share)
  const cur = topics.find((x) => x.topic_id === sel) || topics[0]
  const max = topics[0].share
  const runAi = async (refresh) => {
    setAi((s) => ({ ...s, [cur.topic_id]: { loading: true, data: s[cur.topic_id]?.data } }))
    try { const d = await api.aiInsights({ scope: 'topic', id: String(cur.topic_id), refresh }); setAi((s) => ({ ...s, [cur.topic_id]: { data: d } })) } catch (e) { setAi((s) => ({ ...s, [cur.topic_id]: { error: errorMessage(e) } })) }
  }
  const a = ai[cur.topic_id] || {}
  const trend = cur.trend || []
  const recent = trend.slice(-12); const prev = trend.slice(-24, -12)
  const avg = (xs) => xs.reduce((s, x) => s + x.share, 0) / (xs.length || 1)
  const change = prev.length ? avg(recent) - avg(prev) : null

  return (
    <div className="grid xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)] gap-5 items-start">
      <Card title={`${topics.length} chủ đề phàn nàn`} subtitle={`${t.data.model} trên ${nf(t.data.n_negative)} đánh giá 1–2 sao · chọn để xem chi tiết`} pad={false}>
        <div className="px-2 pb-2">
          {topics.map((x) => (
            <button key={x.topic_id} onClick={() => { setSel(x.topic_id); app.setFocusTopic(x.topic_id) }}
              className={`w-full text-left rounded-lg px-3 py-2.5 my-0.5 ${x.topic_id === cur.topic_id ? 'bg-primarySoft' : 'hover:bg-slate-50'}`}>
              <div className="flex items-center gap-2">
                <span className={`flex-1 text-[13.5px] ${x.topic_id === cur.topic_id ? 'font-semibold text-ink' : 'text-ink'}`}>{x.name}</span>
                <span className="text-[12.5px] tabular-nums text-muted">{pct(x.share)}</span>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full" style={{ width: `${(x.share / max) * 100}%`, background: COLOR.neg }} /></div>
              <div className="text-[11.5px] text-muted mt-1 truncate">{x.keywords.slice(0, 5).join(' · ')}</div>
            </button>
          ))}
        </div>
      </Card>

      <div className="space-y-5">
        <Card title={cur.name} subtitle={`${nf(cur.n_reviews)} đánh giá tiêu cực · ${pct(cur.share)} tổng số đánh giá 1–2 sao`}>
          <div className="flex flex-wrap gap-1.5">
            {cur.keywords.map((k, i) => <span key={k} className="rounded-full px-2.5 py-1 text-[12.5px]" style={{ background: `rgba(214,69,69,${0.16 - i * 0.012})`, color: '#8f2b2b' }}>{k}</span>)}
          </div>
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-emerald-50/70 border border-emerald-100 px-3 py-2.5 text-[13px]">
            <Lightbulb size={16} className="text-emerald-700 mt-0.5 shrink-0" /><span><b className="text-ink">Gợi ý hành động:</b> {cur.suggestion}</span>
          </div>
          <div className="mt-5 flex items-baseline gap-2">
            <div className="text-[13px] font-semibold text-ink flex-1">Tỷ trọng chủ đề trong đánh giá tiêu cực theo tháng</div>
            {change != null && <div className="text-[12px]" style={{ color: change > 0.005 ? COLOR.high : change < -0.005 ? COLOR.low : COLOR.muted }}>12 tháng gần nhất {change > 0 ? 'tăng' : 'giảm'} {nf(Math.abs(change) * 100, 1)} điểm % so với 12 tháng trước</div>}
          </div>
          <div className="h-56 mt-2">
            <ResponsiveContainer>
              <LineChart data={trend} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
                <CartesianGrid stroke={COLOR.grid} vertical={false} />
                <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={28} />
                <YAxis tickFormatter={(v) => pct(v, 0)} {...axisProps} />
                <Tooltip content={<ChartTip labelFormat={monthLabel} rows={(d) => [['Tỷ trọng', pct(d.share), COLOR.neg]]} />} />
                <Line dataKey="share" stroke={COLOR.neg} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="text-[11.5px] text-muted">36 tháng gần nhất có ≥ 20 đánh giá tiêu cực</div>
        </Card>

        <Card title="Đánh giá tiêu biểu" subtitle="3 đánh giá có mức khớp chủ đề cao nhất">
          <div className="space-y-2">{cur.samples.map((s) => <ReviewQuote key={s.review_id} r={s} />)}</div>
          <div className="flex flex-wrap gap-2 mt-3">
            {[...new Set(cur.samples.map((s) => s.product_id))].map((pid) => <button key={pid} className="chip font-mono" onClick={() => app.openProduct(pid)}>{pid}</button>)}
          </div>
        </Card>

        <Card title="Nguyên nhân sâu và giải pháp" subtitle="Trợ lý AI đọc tối đa 30 đánh giá của chủ đề (≥ 15 từ, ưu tiên 12 tháng gần nhất, khớp chủ đề nhất); mỗi nguyên nhân trích review_id làm bằng chứng"
          action={<button className="btn btn-ai" disabled={a.loading} onClick={() => runAi(!!a.data)}>{a.loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}{a.data ? 'Phân tích lại' : 'Phân tích bằng AI'}</button>}>
          {a.error && <ErrorBox error={a.error} />}
          {a.loading && !a.data && <Loading h="h-24" label="Đang gửi đánh giá cho trợ lý AI…" />}
          {a.data ? <InsightView data={a.data} /> : !a.loading && <div className="text-[13px] text-muted">Bấm “Phân tích bằng AI” để nhận danh sách nguyên nhân cụ thể hơn tên chủ đề, kèm hành động và chỉ số theo dõi.</div>}
          <button className="btn mt-3" onClick={() => app.openChat(`Chủ đề phàn nàn "${cur.name}" chiếm bao nhiêu và người bán nên làm gì?`)}><Bot size={15} />Hỏi trợ lý về chủ đề này</button>
        </Card>
      </div>
    </div>
  )
}
