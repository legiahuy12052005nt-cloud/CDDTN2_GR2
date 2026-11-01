// Định dạng số kiểu Việt Nam và bảng màu dùng chung (màu cảm xúc: đỏ ↔ xám ↔ xanh; màu rủi ro: bảng trạng thái).
export const nf = (x, d = 0) =>
  x == null || Number.isNaN(Number(x)) ? '–' : Number(x).toLocaleString('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d })
export const pct = (x, d = 1) => (x == null || Number.isNaN(Number(x)) ? '–' : `${nf(x * 100, d)}%`)
export const signed = (x, d = 2) => (x == null ? '–' : `${x > 0 ? '+' : ''}${nf(x, d)}`)
export const monthLabel = (m) => (m ? `${m.slice(5, 7)}/${m.slice(0, 4)}` : '')
export const monthShort = (m) => (m ? `${m.slice(5, 7)}/${m.slice(2, 4)}` : '')

export const COLOR = {
  ink: '#0f2438', text: '#334155', muted: '#64748b', grid: '#e7ebf1', axis: '#94a3b8',
  primary: '#2a78d6', primaryDark: '#1c5cab', primarySoft: '#e8f1fc',
  neg: '#d64545', neu: '#9aa3ad', pos: '#2a78d6',
  ai: '#6250d6', aiSoft: '#efedfc',
  high: '#d03b3b', medium: '#d98a00', low: '#0f9d58', insufficient: '#94a3b8',
}

export const SENT = {
  neg: { label: 'Tiêu cực', color: COLOR.neg, soft: '#fdecec', range: '1–2 sao' },
  neu: { label: 'Trung tính', color: COLOR.neu, soft: '#f1f3f5', range: '3 sao' },
  pos: { label: 'Tích cực', color: COLOR.pos, soft: '#e8f1fc', range: '4–5 sao' },
}

export const RISK = {
  high: { label: 'Rủi ro cao', short: 'Cao', color: COLOR.high, soft: '#fdecec' },
  medium: { label: 'Rủi ro trung bình', short: 'Trung bình', color: COLOR.medium, soft: '#fff4dc' },
  low: { label: 'Ổn định', short: 'Thấp', color: COLOR.low, soft: '#e6f6ed' },
  insufficient: { label: 'Chưa đủ dữ liệu', short: 'Chưa đủ DL', color: COLOR.insufficient, soft: '#f1f5f9' },
}

export const starColor = (s) => (s <= 2 ? COLOR.neg : s === 3 ? COLOR.neu : COLOR.pos)
export const sentOfStar = (s) => (s <= 2 ? 'neg' : s === 3 ? 'neu' : 'pos')

const makeStore = (kind) => ({
  get(key, fallback) {
    try { const v = window[kind].getItem(key); return v ? JSON.parse(v) : fallback } catch { return fallback }
  },
  set(key, value) {
    try { window[kind].setItem(key, JSON.stringify(value)) } catch { /* bỏ qua khi trình duyệt chặn lưu trữ */ }
  },
})
export const store = makeStore('localStorage')          // lưu lâu dài trên trình duyệt
export const sessionStore = makeStore('sessionStorage') // chỉ trong phiên (đóng tab là mất) – lịch sử dự đoán FR-17
