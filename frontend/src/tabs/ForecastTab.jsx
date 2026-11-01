import { useEffect, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Search } from 'lucide-react'
import { api } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, monthLabel, monthShort, nf, signed } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Card, ChartTip, ErrorBox, Loading, Note, Segmented, axisProps } from '../components/ui.jsx'
import { niceAxis } from './OverviewTab.jsx'

export default function ForecastTab() {
  const app = useApp()
  const [scope, setScope] = useState('all')
  const [pid, setPid] = useState(null)
  const [months, setMonths] = useState(12)
  const [q, setQ] = useState('')
  const [qq, setQq] = useState('')
  useEffect(() => { const t = setTimeout(() => setQq(q), 300); return () => clearTimeout(t) }, [q])
  const list = useApi(() => api.products({ forecastable: true, sort: 'n_reviews', page_size: 12, q: qq }), [qq], { skip: scope !== 'product' })
  const fc = useApi(() => api.forecast({ months, product_id: scope === 'product' ? pid : undefined }), [months, scope, pid], { skip: scope === 'product' && !pid })
  useEffect(() => { if (scope === 'product' && !pid && list.data?.items?.length) setPid(list.data.items[0].product_id) }, [scope, pid, list.data])

  const d = fc.data
  const hist = d?.history || []
  const chart = [...hist.map((h) => ({ month: h.month, actual: h.sat_index, n: h.n })), ...(d?.forecast || []).map((f) => ({ month: f.month, fc: f.sat_index, band: [f.lo, f.hi] }))]
  if (hist.length && d?.forecast?.length) { const i = hist.length - 1; chart[i] = { ...chart[i], fc: chart[i].actual, band: [chart[i].actual, chart[i].actual] } }
  const lastH = hist[hist.length - 1]; const lastF = d?.forecast?.[d.forecast.length - 1]

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-line shadow-card p-4 flex flex-wrap items-center gap-4">
        <div><div className="text-[12px] text-muted mb-1">Phạm vi</div><Segmented value={scope} onChange={(v) => { setScope(v); if (v === 'all') setPid(null) }} options={[['all', 'Toàn bộ dữ liệu'], ['product', 'Từng sản phẩm']]} /></div>
        <div><div className="text-[12px] text-muted mb-1">Số tháng dự báo</div><Segmented value={months} onChange={setMonths} options={[[3, '3 tháng'], [6, '6 tháng'], [12, '12 tháng']]} /></div>
        {scope === 'product' && (
          <div className="flex-1 min-w-[280px]">
            <div className="text-[12px] text-muted mb-1">Sản phẩm đủ điều kiện (≥ 36 tháng có đánh giá)</div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" /><input className="input pl-8 w-44 font-mono" placeholder="Tìm mã" value={q} onChange={(e) => setQ(e.target.value.toUpperCase())} /></span>
              {(list.data?.items || []).slice(0, 8).map((p) => (
                <button key={p.product_id} onClick={() => setPid(p.product_id)} className={`chip font-mono ${pid === p.product_id ? '!border-primary !text-primary bg-primarySoft' : ''}`}>{p.product_id}<span className="text-muted font-sans">· {nf(p.n_reviews)}</span></button>
              ))}
              {list.data && list.data.items.length === 0 && <span className="text-[12.5px] text-muted">Không có sản phẩm khớp</span>}
            </div>
          </div>
        )}
      </div>

      {scope === 'product' && !pid ? (list.loading || !list.data ? <Loading h="h-96" /> : <Note>Chọn một sản phẩm đủ điều kiện ở trên (hoặc đổi từ khóa tìm) để xem dự báo.</Note>)
        : fc.error ? <ErrorBox error={fc.error} /> : fc.loading || !d || d.scope !== scope ? <Loading h="h-96" /> : (
        <div className="grid xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-5 items-start">
          <Card title={scope === 'all' || !pid ? 'Chỉ số hài lòng toàn bộ: thực tế và dự báo' : `Chỉ số hài lòng của ${pid}`}
            subtitle={d.eligible ? `${d.model} · vùng mờ là khoảng tin cậy 95%` : d.message}
            action={scope === 'product' && pid && <button className="btn" onClick={() => app.openProduct(pid)}>Chi tiết sản phẩm</button>}>
            <div className="h-80">
              <ResponsiveContainer>
                <ComposedChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke={COLOR.grid} vertical={false} />
                  <XAxis dataKey="month" tickFormatter={monthShort} {...axisProps} minTickGap={28} />
                  <YAxis {...(scope === 'all' ? niceAxis(chart) : { domain: [0, 100], ticks: [0, 25, 50, 75, 100] })} tickFormatter={(v) => nf(v, 0)} {...axisProps} />
                  <Tooltip content={<ChartTip labelFormat={monthLabel} rows={(x) => x.actual != null ? [['Thực tế', nf(x.actual, 1), COLOR.ink], ['Số đánh giá', nf(x.n)]] : [['Dự báo', nf(x.fc, 1), COLOR.primary], ['Khoảng 95%', `${nf(x.band[0], 1)} – ${nf(x.band[1], 1)}`]]} />} />
                  {lastH && d.forecast.length > 0 && <ReferenceLine x={lastH.month} stroke={COLOR.axis} strokeDasharray="2 3" label={{ value: 'bắt đầu dự báo', position: 'insideTopLeft', fontSize: 11, fill: COLOR.muted }} />}
                  <Area dataKey="band" stroke="none" fill={COLOR.primary} fillOpacity={0.14} isAnimationActive={false} />
                  <Line dataKey="actual" stroke={COLOR.ink} strokeWidth={2} dot={scope === 'product' ? { r: 2 } : false} isAnimationActive={false} />
                  <Line dataKey="fc" stroke={COLOR.primary} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex gap-4 text-[12px] text-muted mt-2">
              <span className="inline-flex items-center gap-1.5"><span className="w-4 h-0.5 bg-ink" />Thực tế ({scope === 'all' ? `tháng có ≥ ${nf(d.series?.threshold_per_month)} đánh giá` : 'tháng có đánh giá'})</span>
              <span className="inline-flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed border-primary" />Dự báo</span>
            </div>
            {scope === 'product' && d.eligible && <div className="mt-3"><Note tone="warn">{d.message}</Note></div>}
          </Card>

          <div className="space-y-5">
            {d.eligible && lastF && (
              <Card title="Tóm tắt dự báo">
                <div className="grid grid-cols-2 gap-4">
                  <div><div className="text-[12px] text-muted">Thực tế {monthLabel(lastH?.month)}</div><div className="text-[24px] font-semibold tabular-nums text-ink">{nf(lastH?.sat_index, 1)}</div></div>
                  <div><div className="text-[12px] text-muted">Dự báo {monthLabel(lastF.month)}</div><div className="text-[24px] font-semibold tabular-nums text-primary">{nf(lastF.sat_index, 1)}</div>
                    <div className="text-[12px]" style={{ color: lastF.sat_index < lastH?.sat_index ? COLOR.high : COLOR.low }}>{signed(lastF.sat_index - (lastH?.sat_index || 0), 1)} điểm</div></div>
                </div>
                {d.backtest && (
                  <div className="mt-4 rounded-lg bg-slate-50 p-3 text-[13px]">
                    <div className="font-medium text-ink">Kiểm tra lùi 12 tháng{d.backtest.test_from ? ` (${monthLabel(d.backtest.test_from)} – ${monthLabel(d.backtest.test_to)})` : ''}</div>
                    <div className="mt-2 space-y-1.5">
                      <Err l={`Mô hình ${d.model?.split(' ')[0]}`} v={d.backtest.mae_model} max={Math.max(d.backtest.mae_model, d.backtest.mae_naive)} c={COLOR.primary} />
                      <Err l="Ngây thơ (giữ giá trị cuối)" v={d.backtest.mae_naive} max={Math.max(d.backtest.mae_model, d.backtest.mae_naive)} c={COLOR.axis} />
                    </div>
                    <div className="text-[12px] text-muted mt-2">Sai số tuyệt đối trung bình (MAE), đơn vị điểm chỉ số 0–100. {d.backtest.mae_model < d.backtest.mae_naive ? 'Mô hình tốt hơn cách đoán ngây thơ.' : 'Mô hình chưa tốt hơn cách đoán ngây thơ – đọc kết quả thận trọng.'}</div>
                  </div>
                )}
              </Card>
            )}
            {d.eligible && (
              <Card title="Giá trị dự báo" pad={false}>
                <table className="tbl">
                  <thead><tr><th>Tháng</th><th className="text-right">Chỉ số</th><th className="text-right">Khoảng tin cậy 95%</th></tr></thead>
                  <tbody>{d.forecast.map((f) => <tr key={f.month}><td>{monthLabel(f.month)}</td><td className="text-right font-medium text-ink">{nf(f.sat_index, 1)}</td><td className="text-right text-muted">{nf(f.lo, 1)} – {nf(f.hi, 1)}</td></tr>)}</tbody>
                </table>
              </Card>
            )}
            {scope === 'all' && <Note>Chuỗi toàn bộ chỉ dùng tháng có đủ đánh giá ({d.series?.series_start && monthLabel(d.series.series_start)} – {d.series?.series_end && monthLabel(d.series.series_end)}, {d.series?.n_months} tháng) và bỏ tháng cuối chưa trọn để tránh nhiễu. Mô hình ETS có xu hướng giảm chấn: dự báo đi theo xu hướng gần đây nhưng phẳng dần.</Note>}
          </div>
        </div>
      )}
    </div>
  )
}

function Err({ l, v, max, c }) {
  return (
    <div className="flex items-center gap-2 text-[12.5px]">
      <span className="w-44 truncate">{l}</span>
      <span className="flex-1 h-2.5 rounded bg-white"><span className="block h-2.5 rounded" style={{ width: `${(v / (max || 1)) * 100}%`, background: c }} /></span>
      <span className="w-10 text-right tabular-nums font-medium">{nf(v, 2)}</span>
    </div>
  )
}
