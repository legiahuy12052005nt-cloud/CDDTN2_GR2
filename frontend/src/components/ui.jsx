// Bộ thành phần giao diện dùng chung: thẻ, chỉ số, nhãn, trạng thái tải/lỗi/trống, chú giải biểu đồ.
import { AlertTriangle, CheckCircle2, CircleDashed, Info, Loader2, ShieldAlert, Star } from 'lucide-react'
import { COLOR, RISK, SENT, nf } from '../lib/format.js'

export function Card({ title, subtitle, action, children, className = '', pad = true, id }) {
  return (
    <section id={id} className={`bg-white rounded-xl border border-line shadow-card ${className}`}>
      {(title || action) && (
        <header className="flex items-start gap-3 px-5 pt-4">
          <div className="flex-1 min-w-0">
            {title && <h3 className="text-[15px] font-semibold text-ink leading-snug">{title}</h3>}
            {subtitle && <p className="text-[12.5px] text-muted mt-0.5 leading-snug">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={pad ? 'p-5 pt-3' : ''}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, sub, tone, icon: Icon, onClick }) {
  const Comp = onClick ? 'button' : 'div'
  return (
    <Comp onClick={onClick} className={`text-left bg-white rounded-xl border border-line shadow-card px-4 py-3.5 ${onClick ? 'hover:border-primary/50 focus-visible:outline-primary' : ''}`}>
      <div className="flex items-center gap-1.5 text-[12.5px] text-muted">
        {Icon && <Icon size={14} style={{ color: tone || COLOR.muted }} />}
        <span>{label}</span>
      </div>
      <div className="mt-1 text-[22px] font-semibold tabular-nums text-ink leading-tight" style={tone ? { color: tone } : undefined}>{value}</div>
      {sub && <div className="text-[12px] text-muted mt-0.5">{sub}</div>}
    </Comp>
  )
}

export function RiskBadge({ level, compact = false }) {
  const r = RISK[level] || RISK.insufficient
  const Icon = level === 'high' ? ShieldAlert : level === 'medium' ? AlertTriangle : level === 'low' ? CheckCircle2 : CircleDashed
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap"
      style={{ background: r.soft, color: r.color }}>
      <Icon size={12} />{compact ? r.short : r.label}
    </span>
  )
}

export function SentBadge({ s, children }) {
  const x = SENT[s] || SENT.neu
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium" style={{ background: x.soft, color: s === 'neu' ? '#55606b' : x.color }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: x.color }} />{children || x.label}
    </span>
  )
}

export function Stars({ value, size = 14 }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${nf(value, 1)} sao`}>
      {[1, 2, 3, 4, 5].map((i) => {
        const fill = Math.max(0, Math.min(1, value - i + 1))
        return (
          <span key={i} className="relative inline-block" style={{ width: size, height: size }}>
            <Star size={size} className="absolute inset-0 text-slate-300" fill="currentColor" strokeWidth={0} />
            <span className="absolute inset-0 overflow-hidden" style={{ width: `${fill * 100}%` }}>
              <Star size={size} className="text-amber-400" fill="currentColor" strokeWidth={0} />
            </span>
          </span>
        )
      })}
    </span>
  )
}

export function Loading({ label = 'Đang tải dữ liệu…', h = 'h-40' }) {
  return (
    <div className={`flex items-center justify-center gap-2 text-muted text-sm ${h}`}>
      <Loader2 size={16} className="animate-spin" />{label}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-800">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && <button className="underline underline-offset-2" onClick={onRetry}>Thử lại</button>}
    </div>
  )
}

export function Note({ children, tone = 'info', icon: Icon = Info }) {
  const tones = { info: 'bg-primarySoft text-[#1c4f8f] border-[#cfe0f6]', warn: 'bg-amber-50 text-amber-900 border-amber-200', ai: 'bg-aiSoft text-[#3b2f99] border-[#ddd8fa]' }
  return (
    <div className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[13px] leading-relaxed ${tones[tone]}`}>
      <Icon size={16} className="mt-0.5 shrink-0" /><div className="flex-1">{children}</div>
    </div>
  )
}

export function Empty({ title, children, icon: Icon = CircleDashed }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-6 text-muted">
      <Icon size={28} className="text-slate-300 mb-2" />
      <div className="text-sm font-medium text-text">{title}</div>
      {children && <div className="text-[13px] mt-1 max-w-md">{children}</div>}
    </div>
  )
}

export function Segmented({ value, onChange, options, size = 'sm' }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5" role="radiogroup">
      {options.map(([v, label]) => (
        <button key={String(v)} role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={`rounded-md ${size === 'sm' ? 'px-2.5 py-1 text-[12.5px]' : 'px-3 py-1.5 text-sm'} ${value === v ? 'bg-white text-ink shadow-sm font-medium' : 'text-muted hover:text-ink'}`}>
          {label}
        </button>
      ))}
    </div>
  )
}

// options: [[giá trị, nhãn, disabled?], …] – phần tử thứ 3 = true thì lựa chọn bị khóa (ví dụ mâu thuẫn với bộ lọc khác)
export function Select({ value, onChange, options, label, className = '', invalid = false }) {
  return (
    <label className={`flex flex-col gap-1 text-[12px] text-muted ${className}`}>
      {label}
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value)} aria-invalid={invalid || undefined}
        className={`h-9 rounded-lg border bg-white px-2.5 text-[13px] text-ink focus:outline-none focus:ring-2 ${invalid ? 'border-red-400 focus:ring-red-200' : 'border-line focus:ring-primary/30'}`}>
        {options.map(([v, l, dis]) => <option key={String(v)} value={v} disabled={!!dis}>{l}</option>)}
      </select>
    </label>
  )
}

export function Pager({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex items-center justify-between text-[12.5px] text-muted pt-3">
      <span>{nf(total)} kết quả · trang {page}/{nf(pages)}</span>
      <div className="flex gap-1">
        <button className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>Trước</button>
        <button className="btn" disabled={page >= pages} onClick={() => onPage(page + 1)}>Sau</button>
      </div>
    </div>
  )
}

// Chú giải khi rê chuột lên biểu đồ (Recharts)
export function ChartTip({ active, payload, label, labelFormat, rows }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 shadow-lg text-[12.5px] min-w-[150px]">
      <div className="font-medium text-ink mb-1">{labelFormat ? labelFormat(label, p) : label}</div>
      {(rows ? rows(p) : payload.map((x) => [x.name, x.value, x.color])).map(([k, v, c], i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          {c && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: c }} />}
          <span className="text-muted flex-1">{k}</span>
          <span className="tabular-nums text-ink font-medium">{v}</span>
        </div>
      ))}
    </div>
  )
}

export const axisProps = { tick: { fontSize: 11, fill: COLOR.muted }, axisLine: { stroke: COLOR.grid }, tickLine: false }

// Thanh tỷ lệ ngang mảnh – dùng trong bảng
export function Bar({ value, max = 1, color = COLOR.primary, w = 'w-24' }) {
  return (
    <span className={`inline-block h-1.5 rounded-full bg-slate-100 align-middle ${w}`}>
      <span className="block h-1.5 rounded-full" style={{ width: `${Math.min(100, (value / (max || 1)) * 100)}%`, background: color }} />
    </span>
  )
}

export function ReviewQuote({ r, highlight }) {
  return (
    <div className="rounded-lg border border-line bg-slate-50/60 px-3 py-2.5 text-[13px]">
      <div className="flex items-center gap-2 text-[12px] text-muted mb-1 flex-wrap">
        <Stars value={r.score} size={12} />
        {r.date && <span>{r.date}</span>}
        {r.product_id && <span className="font-mono text-[11.5px]">{r.product_id}</span>}
        <span className="ml-auto text-[11.5px]">#{r.review_id}</span>
      </div>
      {r.summary && <div className="font-medium text-ink">{r.summary}</div>}
      {r.text && <p className="text-text leading-relaxed mt-0.5">{highlight ? highlight(r.text) : r.text}</p>}
    </div>
  )
}

// Loại tín hiệu cảnh báo: đang giảm điểm (bị đánh giá thấp dần) / tiêu cực cao kéo dài (điểm không giảm)
const SIGNAL = {
  decline: { label: 'Đang giảm điểm', color: COLOR.high, soft: '#fdecec' },
  negative: { label: 'Tiêu cực kéo dài', color: COLOR.medium, soft: '#fff4dc' },
}

export function SignalTag({ s }) {
  const v = SIGNAL[s]
  if (!v) return null
  return <span className="inline-block mr-1.5 mb-0.5 rounded px-1.5 py-[1px] text-[11px] font-medium align-middle" style={{ color: v.color, background: v.soft }}>{v.label}</span>
}
