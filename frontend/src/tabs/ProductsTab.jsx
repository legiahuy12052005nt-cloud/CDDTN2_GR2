import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Download, Search } from 'lucide-react'
import { api } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, RISK, monthLabel, nf, pct, signed } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Card, ErrorBox, Loading, Note, Pager, RiskBadge, Select, SignalTag } from '../components/ui.jsx'

const SORTS = [['risk', 'Mức rủi ro'], ['neg_rate', 'Tỷ lệ tiêu cực 3 tháng'], ['delta', 'Thay đổi điểm 3 tháng'], ['n_reviews', 'Số đánh giá'], ['avg_score', 'Điểm TB toàn kỳ']]

export default function ProductsTab() {
  const app = useApp()
  const [q, setQ] = useState('')
  const [qq, setQq] = useState('')
  const [risk, setRisk] = useState('')
  const [sort, setSort] = useState('risk')
  const [order, setOrder] = useState('desc')
  const [minRev, setMinRev] = useState('')
  const [page, setPage] = useState(1)
  useEffect(() => { const t = setTimeout(() => { setQq(q); setPage(1) }, 300); return () => clearTimeout(t) }, [q])
  const r = useApi(() => api.products({ q: qq, risk, sort, order, page, page_size: 15, min_reviews: minRev || undefined }), [qq, risk, sort, order, page, minRev])
  const counts = r.data?.counts || {}
  const total = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {['high', 'medium', 'low', 'insufficient'].map((k) => (
          <button key={k} onClick={() => { setRisk(risk === k ? '' : k); setPage(1) }}
            className={`text-left rounded-xl border bg-white px-4 py-3 shadow-card ${risk === k ? 'ring-2' : 'border-line hover:border-slate-300'}`}
            style={risk === k ? { borderColor: RISK[k].color, '--tw-ring-color': RISK[k].color + '33' } : undefined}>
            <RiskBadge level={k} />
            <div className="text-[24px] font-semibold tabular-nums mt-1.5" style={{ color: k === 'insufficient' ? COLOR.ink : RISK[k].color }}>{nf(counts[k])}</div>
            <div className="text-[12px] text-muted">{pct((counts[k] || 0) / (total || 1))} sản phẩm</div>
          </button>
        ))}
      </div>
      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <Note>Mỗi sản phẩm được so sánh 3 tháng gần nhất (đến {monthLabel(r.data?.as_of)}) với 3 tháng liền trước, mỗi cửa sổ cần ≥ 10 đánh giá.
            Rủi ro cao: điểm TB giảm ≥ 0,5 sao hoặc tỷ lệ tiêu cực ≥ 40%; trung bình: giảm ≥ 0,25 sao hoặc ≥ 25%.
            Có hai loại tín hiệu: <b>Đang giảm điểm</b> (sản phẩm bị đánh giá thấp dần) và <b>Tiêu cực kéo dài</b> (điểm không giảm nhưng tỷ lệ 1–2 sao vẫn cao).
            Khi sắp theo mức rủi ro, trong cùng một mức sản phẩm giảm điểm mạnh nhất đứng trước. Phần lớn sản phẩm có ít đánh giá nên “chưa đủ dữ liệu”.</Note>
        </div>
        <Backtest className="lg:col-span-2" bt={r.data?.backtest} />
      </div>

      <Card pad={false}>
        <div className="flex flex-wrap items-end gap-3 px-5 pt-4 pb-3">
          <label className="flex flex-col gap-1 text-[12px] text-muted">Tìm mã sản phẩm
            <span className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" /><input className="input pl-8 w-56 font-mono" value={q} onChange={(e) => setQ(e.target.value.toUpperCase())} placeholder="VD: B007" /></span>
          </label>
          <Select label="Mức rủi ro" value={risk} onChange={(v) => { setRisk(v); setPage(1) }} options={[['', 'Tất cả'], ...Object.entries(RISK).map(([k, v]) => [k, v.label])]} className="w-44" />
          <Select label="Sắp xếp theo" value={sort} onChange={(v) => { setSort(v); setPage(1) }} options={SORTS} className="w-52" />
          <button className="btn" onClick={() => setOrder(order === 'desc' ? 'asc' : 'desc')} title="Đảo thứ tự">{order === 'desc' ? <ArrowDown size={14} /> : <ArrowUp size={14} />}{order === 'desc' ? 'Giảm dần' : 'Tăng dần'}</button>
          <Select label="Số đánh giá tối thiểu" value={minRev} onChange={(v) => { setMinRev(v); setPage(1) }} options={[['', 'Không lọc'], ['10', '≥ 10'], ['50', '≥ 50'], ['100', '≥ 100'], ['300', '≥ 300']]} className="w-40" />
          <span className="flex-1" />
          <a className="btn" href={api.exportUrl('product_risk')}><Download size={14} />Tải CSV</a>
        </div>
        {r.error ? <div className="px-5 pb-4"><ErrorBox error={r.error} /></div> : r.loading && !r.data ? <Loading /> : (
          <div className={`overflow-x-auto ${r.loading ? 'opacity-60' : ''}`}>
            <table className="tbl">
              <thead><tr>
                <th>Sản phẩm</th><th>Mức rủi ro</th><th className="text-right">Số ĐG</th><th className="text-right">Điểm TB toàn kỳ</th>
                <th className="text-right">ĐG 3 tháng</th><th className="text-right">TB 3 tháng trước → gần nhất</th><th className="text-right">Thay đổi</th><th className="text-right">Tiêu cực 3 tháng</th><th>Lý do</th><th>Dự báo</th>
              </tr></thead>
              <tbody>
                {r.data.items.map((p) => (
                  <tr key={p.product_id} className="clickable" onClick={() => app.openProduct(p.product_id)}>
                    <td className="font-mono text-[12.5px] text-ink">{p.product_id}</td>
                    <td><RiskBadge level={p.risk_level} compact /></td>
                    <td className="text-right">{nf(p.n_reviews)}</td>
                    <td className="text-right">{nf(p.avg_score, 2)}</td>
                    <td className="text-right">{nf(p.n_3m)} <span className="text-muted">/ {nf(p.n_prev_3m)}</span></td>
                    <td className="text-right whitespace-nowrap">{p.avg_prev_3m != null ? <>{nf(p.avg_prev_3m, 2)} → <b className="text-ink">{nf(p.avg_3m, 2)}</b></> : '–'}</td>
                    <td className="text-right" style={{ color: p.delta == null ? undefined : p.delta <= -0.25 ? COLOR.high : p.delta > 0 ? COLOR.low : undefined }}>{signed(p.delta)}</td>
                    <td className="text-right">{pct(p.neg_rate_3m, 0)}</td>
                    <td className="text-[12.5px] text-text max-w-[280px]">
                      {p.signal && <SignalTag s={p.signal} />}
                      {p.reason || <span className="text-muted">–</span>}
                    </td>
                    <td className="text-[12px]">{p.forecastable ? <span className="text-emerald-700">Có ({p.n_active_months} th.)</span> : <span className="text-muted">{p.n_active_months} th.</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {r.data.items.length === 0 && <div className="py-8 text-center text-[13px] text-muted">Không có sản phẩm khớp bộ lọc.</div>}
          </div>
        )}
        {r.data && <div className="px-5 pb-4"><Pager page={page} pageSize={15} total={r.data.page.total} onPage={setPage} /></div>}
      </Card>
    </div>
  )
}

// Kiểm tra ngược quy tắc (notebook 05): gắn mức tại 6 và 3 tháng trước, xem tỷ lệ tiêu cực ở 3 tháng tiếp theo
function Backtest({ bt, className = '' }) {
  const s = bt?.summary
  if (!s || s.high?.neg_next == null) return null
  const max = Math.max(...['high', 'medium', 'low'].map((k) => s[k]?.neg_next || 0), 0.01)
  return (
    <div className={`rounded-xl border border-line bg-white px-4 py-3 shadow-card ${className}`}>
      <div className="text-[13px] font-semibold text-ink">Quy tắc có báo đúng không? – kiểm tra ngược</div>
      <div className="text-[11.5px] text-muted mt-0.5">Gắn mức tại {bt.as_of_points.map(monthLabel).join(' và ')}, rồi xem tỷ lệ tiêu cực ở 3 tháng tiếp theo – dữ liệu quy tắc chưa nhìn thấy</div>
      <div className="mt-2.5 space-y-1.5">
        {['high', 'medium', 'low'].map((k) => s[k]?.neg_next != null && (
          <div key={k} className="flex items-center gap-2 text-[12.5px]">
            <span className="w-24 shrink-0" style={{ color: RISK[k].color }}>{RISK[k].short === 'Thấp' ? 'Ổn định' : RISK[k].short}</span>
            <span className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden"><span className="block h-full rounded-full" style={{ width: `${(s[k].neg_next / max) * 100}%`, background: RISK[k].color }} /></span>
            <span className="w-12 text-right tabular-nums font-medium text-ink">{pct(s[k].neg_next, 1)}</span>
            <span className="w-14 text-right text-[11.5px] text-muted">{nf(s[k].n_products)} SP</span>
          </div>
        ))}
      </div>
      <div className="text-[11.5px] text-muted mt-2">Nhóm bị gắn “Cao” vẫn có tỷ lệ tiêu cực ở 3 tháng sau gấp {nf(s.high.neg_next / (s.low?.neg_next || 1), 1)} lần nhóm ổn định.</div>
    </div>
  )
}
