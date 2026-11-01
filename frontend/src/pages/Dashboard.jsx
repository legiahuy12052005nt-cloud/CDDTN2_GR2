import { useMemo, useState } from 'react'
import { BarChart3, Bot, Brain, FileDown, LayoutDashboard, LineChart, MessageSquareWarning, PackageSearch, RefreshCcw, Wand2 } from 'lucide-react'
import { AppCtx } from '../lib/appContext.js'
import { nf } from '../lib/format.js'
import { BrandMark } from '../components/Brand.jsx'
import Chatbot from '../components/Chatbot.jsx'
import ProductDrawer from '../components/ProductDrawer.jsx'
import OverviewTab from '../tabs/OverviewTab.jsx'
import EdaTab from '../tabs/EdaTab.jsx'
import ModelTab from '../tabs/ModelTab.jsx'
import PredictTab from '../tabs/PredictTab.jsx'
import ProductsTab from '../tabs/ProductsTab.jsx'
import TopicsTab from '../tabs/TopicsTab.jsx'
import ForecastTab from '../tabs/ForecastTab.jsx'
import AiTab from '../tabs/AiTab.jsx'
import ReportTab from '../tabs/ReportTab.jsx'

// 9 tab của Dashboard (báo cáo buổi 4, bảng 4.5)
const TABS = [
  ['overview', 'Tổng quan', LayoutDashboard, OverviewTab],
  ['eda', 'Phân tích (EDA)', BarChart3, EdaTab],
  ['model', 'Mô hình ML', Brain, ModelTab],
  ['predict', 'Tự nhập dự đoán', Wand2, PredictTab],
  ['products', 'Sản phẩm & cảnh báo', PackageSearch, ProductsTab],
  ['topics', 'Chủ đề phàn nàn', MessageSquareWarning, TopicsTab],
  ['forecast', 'Dự báo', LineChart, ForecastTab],
  ['ai', 'Trợ lý AI', Bot, AiTab],
  ['report', 'Báo cáo', FileDown, ReportTab],
]

export default function Dashboard({ health, refreshHealth, onChangeData }) {
  const [tab, setTab] = useState('overview')
  const [product, setProduct] = useState(null)
  const [focusTopic, setFocusTopic] = useState(null)
  const [chat, setChat] = useState({ open: false, prefill: null, nonce: 0 })
  const ds = health?.dataset || {}

  const ctx = useMemo(() => ({
    health, refreshHealth, changeData: onChangeData,
    goTab: (t, opts = {}) => { setTab(t); if (opts.topic != null) setFocusTopic(opts.topic); window.scrollTo({ top: 0 }) },
    openProduct: (pid) => setProduct(pid),
    openChat: (prefill) => setChat((c) => ({ open: true, prefill: prefill || null, nonce: c.nonce + 1 })),
    focusTopic, setFocusTopic,
    pageLabel: TABS.find((t) => t[0] === tab)[1],
    product,
    chat,                                   // tab Trợ lý AI nhúng sẵn khung chat: nhận câu hỏi gợi sẵn qua đây
  }), [health, refreshHealth, onChangeData, tab, product, focusTopic, chat])

  const Current = TABS.find((t) => t[0] === tab)[3]
  return (
    <AppCtx.Provider value={ctx}>
      <div className="min-h-screen">
        <header className="bg-ink text-white">
          <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-3">
            <BrandMark />
            <div className="font-semibold tracking-tight">FoodReview Insight</div>
            <div className="hidden md:block text-[12.5px] text-slate-300 truncate pl-3 ml-1 border-l border-white/15">
              {ds.file_name} · {nf(ds.n_reviews)} đánh giá · {nf(ds.n_products)} sản phẩm · {ds.date_min?.slice(0, 4)}–{ds.date_max?.slice(0, 4)}
            </div>
            <div className="flex-1" />
            <span className={`hidden sm:inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] ${health?.gemini_configured ? 'bg-white/10 text-white' : 'bg-white/5 text-slate-300'}`}
              title={health?.gemini_error || ''}>
              <span className={`w-1.5 h-1.5 rounded-full ${health?.gemini_configured ? (health?.gemini_error ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-slate-400'}`} />
              {health?.gemini_configured ? `Gemini${health?.gemini_model ? ` · ${health.gemini_model}` : ''}` : 'Gemini chưa cấu hình'}
            </span>
            <button className="btn btn-ghost text-white hover:bg-white/10" onClick={onChangeData}><RefreshCcw size={14} />Đổi dữ liệu</button>
          </div>
          <nav className="max-w-[1400px] mx-auto px-4 flex gap-1 overflow-x-auto" aria-label="Các màn hình">
            {TABS.map(([id, label, Icon]) => (
              <button key={id} onClick={() => ctx.goTab(id)} aria-current={tab === id ? 'page' : undefined}
                className={`flex items-center gap-1.5 whitespace-nowrap px-3 h-10 text-[13px] rounded-t-lg ${tab === id ? 'bg-canvas text-ink font-semibold' : 'text-slate-300 hover:text-white hover:bg-white/5'}`}>
                <Icon size={15} />{label}
              </button>
            ))}
          </nav>
        </header>
        <main className="max-w-[1400px] mx-auto px-6 py-6">
          <Current key={tab} />
        </main>
        <footer className="max-w-[1400px] mx-auto px-6 pb-20 pr-20 text-[12px] text-muted">
          Dữ liệu phiên bản {ds.dataset_version} · xử lý lúc {ds.created_at?.replace('T', ' ')} · Đề tài Phân tích & dự báo mức độ hài lòng của khách hàng từ dữ liệu đánh giá thực phẩm trên Amazon
        </footer>
        {product && <ProductDrawer productId={product} onClose={() => setProduct(null)} />}
        {tab !== 'ai' && <Chatbot open={chat.open} prefill={chat.prefill} nonce={chat.nonce} onOpenChange={(o) => setChat((c) => ({ ...c, open: o, prefill: o ? c.prefill : null }))} />}
      </div>
    </AppCtx.Provider>
  )
}
