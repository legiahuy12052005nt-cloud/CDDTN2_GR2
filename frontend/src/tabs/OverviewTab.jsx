import { Area, Bar as RBar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ArrowRight, Brain, MessageSquareWarning, Package, ShieldAlert, Star, ThumbsDown, Users } from 'lucide-react'
import { api } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, monthLabel, monthShort, nf, pct, signed, starColor } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Bar, Card, ChartTip, ErrorBox, Loading, RiskBadge, Stars, Stat, axisProps } from '../components/ui.jsx'

export default function OverviewTab() {
  const app = useApp()
  const kpi = useApi(() => api.kpi(), [])
  const fc = useApi(() => api.forecast({ months: 12 }), [])
  const dist = useApi(() => api.eda('score_dist'), [])
  const risk = useApi(() => api.products({ sort: 'risk', page_size: 6 }), [])
  const topics = useApi(() => api.topics(), [])
  const q = useApi(() => api.quality(), [])

  if (kpi.loading) return <Loading h="h-80" />
  if (kpi.error) return <ErrorBox error={kpi.error} onRetry={kpi.reload} />
  const k = kpi.data
  const hist = fc.data?.history || []
  const last = hist[hist.length - 1]
  const yoy = hist.length > 12 ? last.sat_index - hist[hist.length - 13].sat_index : null
  const next = fc.data?.forecast?.[0]
  const chart = [...hist.map((h) => ({ month: h.month, actual: h.sat_index, n: h.n })), ...(fc.data?.forecast || []).map((f) => ({ month: f.month, fc: f.sat_index, band: [f.lo, f.hi] }))]
  if (chart.length && hist.length) { const i = hist.length - 1; chart[i] = { ...chart[i], fc: chart[i].actual, band: [chart[i].actual, chart[i].actual] } }
  const topTopics = [...(topics.data?.topics || [])].sort((a, b) => b.share - a.share)

  return (
    <div className="space-y-5">
      <div className="grid xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.6fr)] gap-5">
        {/* chỉ số hài lòng – thông tin quan trọng nhất của màn hình */}
        <section className="rounded-xl bg-ink text-white p-6 shadow-card relative overflow-hidden">
          <div className="text-[13px] text-slate-300">Chỉ số hài lòng khách hàng · toàn bộ dữ liệu</div>
          <div className="flex items-end gap-3 mt-2">
            <div className="text-[64px] leading-none font-semibold tabular-nums tracking-tight">{nf(k.satisfaction_index, 1)}</div>
            <div className="pb-2 text-slate-300 text-[14px]">/ 100</div>
          </div>
          <div className="flex items-center gap-2 mt-3 text-[13px] text-slate-200">
            <Stars value={k.avg_score} size={15} /><span className="tabular-nums">{nf(k.avg_score, 2)} sao trung bình trên {nf(k.n_reviews)} đánh giá</span>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-6 pt-5 border-t border-white/10">
            <div>
              <div className="text-[12px] text-slate-400">Tháng gần nhất ({monthLabel(last?.month)})</div>
              <div className="text-[20px] font-semibold tabular-nums mt-0.5">{nf(last?.sat_index, 1)}</div>
              {yoy != null && <div className="text-[12px] mt-0.5" style={{ color: yoy < 0 ? '#ff9b9b' : '#8ee0b0' }}>{signed(yoy, 1)} điểm so với cùng kỳ năm trước</div>}
            </div>
            <div>
              <div className="text-[12px] text-slate-400">Dự báo {monthLabel(next?.month)}</div>
              <div className="text-[20px] font-semibold tabular-nums mt-0.5">{nf(next?.sat_index, 1)}</div>
              <div className="text-[12px] text-slate-400 mt-0.5">95%: {nf(next?.lo, 1)} – {nf(next?.hi, 1)} · {fc.data?.model}</div>
            </div>
          </div>
          <div className="text-[11.5px] text-slate-400 mt-5">Chỉ số = (điểm sao TB − 1) / 4 × 100. Đánh giá 1–2 sao: tiêu cực, 3 sao: trung tính, 4–5 sao: tích cực.</div>
        </section>

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 content-start">
          <Stat icon={Star} label="Đánh giá sau làm sạch" value={nf(k.n_reviews)} sub={`từ ${nf(q.data?.n_rows)} dòng gốc`} />
          <Stat icon={Package} label="Sản phẩm" value={nf(k.n_products)} sub={`${k.date_min?.slice(0, 4)}–${k.date_max?.slice(0, 4)}`} />
          <Stat icon={Users} label="Người đánh giá" value={nf(k.n_users)} sub="đã ẩn danh bằng SHA-1" />
          <Stat icon={ThumbsDown} label="Tỷ lệ tiêu cực" value={pct(k.neg_rate)} tone={COLOR.neg} sub="đánh giá 1–2 sao" />
          <Stat icon={ShieldAlert} label="Sản phẩm rủi ro cao" value={nf(k.n_high_risk_products)} tone={COLOR.high} sub={`tính đến ${monthLabel(k.last_full_month)}`} onClick={() => app.goTab('products')} />
          <Stat icon={Brain} label="F1-macro mô hình" value={nf(k.model_f1_macro, 3)} sub="3 lớp cảm xúc, tập kiểm tra" onClick={() => app.goTab('model')} />
          <Insights className="col-span-2 lg:col-span-3" k={k} hist={hist} yoy={yoy} next={next} topics={topTopics} risk={risk.data} />
        </div>
      </div>

      <div className="grid xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-5">
        <Card title="Chỉ số hài lòng theo tháng và dự báo 12 tháng" subtitle={`Các tháng có ≥ ${nf(fc.data?.series?.threshold_per_month)} đánh giá · đường nét đứt là dự báo, vùng mờ là khoảng tin cậy 95%`}>
          {fc.loading ? <Loading h="h-72" /> : (
            <div className="h-72">
              <ResponsiveContainer>
                <ComposedChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke={COLOR.grid} vertical={false} />
                  <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={28} />
                  <YAxis {...niceAxis(chart)} tickFormatter={(v) => nf(v, 0)} {...axisProps} />
                  <Tooltip content={<ChartTip labelFormat={monthLabel} rows={(d) => d.actual != null ? [['Chỉ số hài lòng', nf(d.actual, 1), COLOR.ink], ['Số đánh giá', nf(d.n)]] : [['Dự báo', nf(d.fc, 1), COLOR.primary], ['Khoảng 95%', `${nf(d.band[0], 1)} – ${nf(d.band[1], 1)}`]]} />} />
                  <Area dataKey="band" stroke="none" fill={COLOR.primary} fillOpacity={0.14} isAnimationActive={false} />
                  <Line dataKey="actual" name="Thực tế" stroke={COLOR.ink} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line dataKey="fc" name="Dự báo" stroke={COLOR.primary} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
          {fc.data?.backtest && <div className="text-[12px] text-muted mt-2">Kiểm tra lùi 12 tháng ({monthLabel(fc.data.backtest.test_from)} – {monthLabel(fc.data.backtest.test_to)}): sai số MAE {nf(fc.data.backtest.mae_model, 2)} điểm, mô hình ngây thơ {nf(fc.data.backtest.mae_naive, 2)} điểm.</div>}
        </Card>

        <Card title="Phân bố số sao" subtitle="Đánh giá 5 sao chiếm đa số – dữ liệu lệch mạnh về tích cực">
          {dist.loading ? <Loading h="h-72" /> : (
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={dist.data?.data || []} margin={{ top: 22, right: 8, bottom: 0, left: -10 }}>
                  <CartesianGrid stroke={COLOR.grid} vertical={false} />
                  <XAxis dataKey="score" tickFormatter={(s) => `${s} sao`} {...axisProps} />
                  <YAxis tickFormatter={(v) => nf(v / 1000, 0) + 'k'} {...axisProps} />
                  <Tooltip cursor={{ fill: '#f1f5f9' }} content={<ChartTip labelFormat={(s) => `${s} sao`} rows={(d) => [['Số đánh giá', nf(d.n), starColor(d.score)], ['Tỷ lệ', pct(d.share)]]} />} />
                  <RBar dataKey="n" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                    {(dist.data?.data || []).map((d) => <Cell key={d.score} fill={starColor(d.score)} />)}
                    <LabelList dataKey="share" position="top" formatter={(v) => pct(v)} style={{ fontSize: 11, fill: COLOR.text }} />
                  </RBar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <div className="grid xl:grid-cols-2 gap-5">
        <Card title="Sản phẩm cần xử lý trước" subtitle="Rủi ro cao: điểm TB 3 tháng gần nhất giảm ≥ 0,5 sao hoặc tỷ lệ tiêu cực ≥ 40%"
          action={<button className="btn btn-ghost text-primary" onClick={() => app.goTab('products')}>Tất cả <ArrowRight size={14} /></button>} pad={false}>
          {risk.loading ? <Loading /> : (
            <table className="tbl">
              <thead><tr><th>Sản phẩm</th><th>Mức</th><th className="text-right">3 tháng trước → gần nhất</th><th className="text-right">Thay đổi</th><th className="text-right">Tiêu cực</th></tr></thead>
              <tbody>
                {(risk.data?.items || []).map((p) => (
                  <tr key={p.product_id} className="clickable" onClick={() => app.openProduct(p.product_id)}>
                    <td className="font-mono text-[12.5px] text-ink">{p.product_id}</td>
                    <td><RiskBadge level={p.risk_level} compact /></td>
                    <td className="text-right tabular-nums">{nf(p.avg_prev_3m, 2)} → <b className="text-ink">{nf(p.avg_3m, 2)}</b></td>
                    <td className="text-right tabular-nums" style={{ color: p.delta == null ? undefined : p.delta <= -0.25 ? COLOR.high : p.delta > 0 ? COLOR.low : undefined }}>{signed(p.delta)}</td>
                    <td className="text-right tabular-nums" style={{ color: COLOR.high }}>{pct(p.neg_rate_3m, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="px-5 py-3 text-[12px] text-muted flex items-center gap-1.5"><AlertTriangle size={13} />{nf(risk.data?.counts?.high)} rủi ro cao · {nf(risk.data?.counts?.medium)} trung bình · {nf(risk.data?.counts?.low)} ổn định · {nf(risk.data?.counts?.insufficient)} sản phẩm chưa đủ đánh giá trong 6 tháng gần nhất</div>
        </Card>

        <Card title="Khách phàn nàn điều gì" subtitle={`Tỷ trọng chủ đề trong ${nf(topics.data?.n_negative)} đánh giá 1–2 sao`}
          action={<button className="btn btn-ghost text-primary" onClick={() => app.goTab('topics')}>Chi tiết <ArrowRight size={14} /></button>}>
          {topics.loading ? <Loading /> : (
            <div className="space-y-2.5">
              {topTopics.map((t) => (
                <button key={t.topic_id} className="w-full flex items-center gap-3 text-left group" onClick={() => app.goTab('topics', { topic: t.topic_id })}>
                  <MessageSquareWarning size={15} className="text-slate-400 group-hover:text-neg shrink-0" />
                  <span className="flex-1 text-[13px] text-ink truncate group-hover:underline underline-offset-2">{t.name}</span>
                  <Bar value={t.share} max={topTopics[0]?.share} color={COLOR.neg} w="w-32" />
                  <span className="w-12 text-right text-[12.5px] tabular-nums text-muted">{pct(t.share)}</span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Dữ liệu đã được xử lý thế nào" subtitle={`${q.data?.file_name || ''} · phiên bản ${k.meta?.dataset_version}`}>
        {q.data && <Pipeline q={q.data} />}
      </Card>

      <Limits k={k} counts={risk.data?.counts} />
    </div>
  )
}

// Trục tung “đẹp”: bước 2 hoặc 5 điểm, vạch chia đều
export function niceAxis(rows) {
  const v = rows.flatMap((r) => [r.actual, r.fc, ...(r.band || [])]).filter((x) => x != null)
  if (!v.length) return { domain: [0, 100] }
  const lo0 = Math.min(...v) - 0.5; const hi0 = Math.max(...v) + 0.5
  const step = hi0 - lo0 > 14 ? 5 : 2
  const lo = Math.floor(lo0 / step) * step; const hi = Math.ceil(hi0 / step) * step
  const ticks = []; for (let t = lo; t <= hi; t += step) ticks.push(t)
  return { domain: [lo, hi], ticks }
}

// Điểm cần chú ý – sinh tự động từ số liệu (không dùng AI)
function Insights({ k, hist, yoy, next, topics, risk, className }) {
  const items = []
  const last = hist[hist.length - 1]
  if (yoy != null) items.push([yoy < 0 ? COLOR.high : COLOR.low, `Chỉ số hài lòng ${monthLabel(last?.month)} là ${nf(last?.sat_index, 1)}, ${yoy < 0 ? 'thấp hơn' : 'cao hơn'} cùng kỳ năm trước ${nf(Math.abs(yoy), 1)} điểm; dự báo ${monthLabel(next?.month)} ở mức ${nf(next?.sat_index, 1)}.`])
  if (topics?.length >= 2) items.push([COLOR.neg, `Hai vấn đề bị phàn nàn nhiều nhất là “${topics[0].name}” (${pct(topics[0].share, 0)}) và “${topics[1].name}” (${pct(topics[1].share, 0)}) đánh giá tiêu cực.`])
  const top = risk?.items?.[0]
  if (top) items.push([COLOR.high, top.signal === 'decline'
    ? `${nf(risk.counts?.high)} sản phẩm rủi ro cao; giảm mạnh nhất ${top.product_id}: điểm TB 3 tháng ${nf(top.avg_prev_3m, 2)} → ${nf(top.avg_3m, 2)} sao (${signed(top.delta)}), ${pct(top.neg_rate_3m, 0)} đánh giá tiêu cực.`
    : `${nf(risk.counts?.high)} sản phẩm rủi ro cao; nặng nhất ${top.product_id} với ${pct(top.neg_rate_3m, 0)} đánh giá tiêu cực trong 3 tháng gần nhất.`])
  if (!items.length) return null
  return (
    <div className={`bg-white rounded-xl border border-line shadow-card px-4 py-3 ${className}`}>
      <div className="text-[13px] font-semibold text-ink mb-1.5">Điểm cần chú ý</div>
      <ul className="space-y-1.5">
        {items.map(([c, t], i) => <li key={i} className="flex gap-2 text-[13px] leading-snug"><span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c }} />{t}</li>)}
      </ul>
    </div>
  )
}

// Giới hạn của phân tích – nói trước để người đọc (và hội đồng) hiểu đúng phạm vi của từng con số
function Limits({ k, counts }) {
  const total = Object.values(counts || {}).reduce((a, b) => a + b, 0)
  const items = [
    ['Nhãn cảm xúc', 'suy ra từ số sao (1–2 tiêu cực, 3 trung tính, 4–5 tích cực), không gán nhãn thủ công. Lớp trung tính khó nhất vì nội dung thường vừa khen vừa chê.'],
    ['Thời gian', `dữ liệu đến ${k.date_max?.split('-').reverse().join('/')}; tháng cuối chưa trọn nên dự báo, cảnh báo, xu hướng chủ đề dừng ở ${monthLabel(k.last_full_month)}. Dự báo là “nếu xu hướng tiếp diễn”, không phải tình hình hiện tại.`],
    ['Cảnh báo', counts ? `chỉ gắn được mức cho sản phẩm có ≥ 10 đánh giá ở mỗi cửa sổ 3 tháng; ${pct((counts.insufficient || 0) / (total || 1), 1)} sản phẩm còn lại “chưa đủ dữ liệu”. Dự báo theo từng sản phẩm có độ tin cậy thấp.` : 'chỉ gắn được mức cho sản phẩm có ≥ 10 đánh giá ở mỗi cửa sổ 3 tháng.'],
    ['Chủ đề', 'NMF gom đánh giá theo từ khóa thống kê; vài chủ đề trùng ngành hàng (cà phê, trà, thú cưng) nên gợi ý hành động chuyển cho bộ phận ngành hàng đó. Tên chủ đề do nhóm đặt sau khi đọc đánh giá mẫu.'],
    ['Trợ lý AI', 'đọc tối đa 30 đánh giá mỗi lần phân tích; mỗi nguyên nhân kèm review_id bằng chứng để người dùng kiểm tra lại trước khi áp dụng.'],
  ]
  return (
    <Card title="Giới hạn cần biết khi đọc kết quả" subtitle="Phạm vi của từng con số trên dashboard">
      <ul className="grid md:grid-cols-2 gap-x-8 gap-y-2">
        {items.map(([h, t]) => <li key={h} className="text-[13px] leading-snug text-text"><b className="text-ink">{h}:</b> {t}</li>)}
      </ul>
    </Card>
  )
}

function Pipeline({ q }) {
  const log = q.clean_log || {}
  const steps = [
    ['Dòng gốc', q.n_rows, null],
    ['Sai số sao / thời gian / nội dung rỗng', -((log.r1_invalid_score || 0) + (log.r2_invalid_time || 0) + (log.r3_empty_text || 0)), 'R1–R3'],
    ['Helpfulness tử số > mẫu số', -(log.r4_helpfulness_invalid || 0), 'R4'],
    ['Bản ghi trùng (cùng người, thời điểm, nội dung)', -(log.r5_duplicates || 0), 'R5'],
    ['Nội dung < 3 từ sau khi bỏ HTML, URL', -(log.r7_too_short || 0), 'R6–R7'],
    ['Đánh giá sạch dùng để phân tích', log.n_clean, 'R8–R9'],
  ]
  return (
    <div className="grid md:grid-cols-6 gap-2">
      {steps.map(([label, v, rule], i) => (
        <div key={i} className={`rounded-lg px-3 py-2.5 ${i === 0 || i === steps.length - 1 ? 'bg-primarySoft' : 'bg-slate-50'}`}>
          <div className="text-[18px] font-semibold tabular-nums" style={{ color: v < 0 ? COLOR.neg : COLOR.ink }}>{v < 0 ? '−' + nf(-v) : nf(Math.abs(v || 0))}</div>
          <div className="text-[12px] text-text leading-snug mt-0.5">{label}</div>
          {rule && <div className="text-[11px] text-muted mt-1">{rule}</div>}
        </div>
      ))}
    </div>
  )
}
