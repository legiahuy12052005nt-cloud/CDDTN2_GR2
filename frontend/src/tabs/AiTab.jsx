import { useState } from 'react'
import { KeyRound, Loader2, Sparkles } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { pct } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import Chatbot from '../components/Chatbot.jsx'
import InsightView from '../components/InsightView.jsx'
import { Card, ErrorBox, Loading, Note, Segmented } from '../components/ui.jsx'

export default function AiTab() {
  const app = useApp()
  const h = app.health
  const [scope, setScope] = useState('product')
  const [id, setId] = useState('')
  const [res, setRes] = useState({})
  const risky = useApi(() => api.products({ risk: 'high', sort: 'risk', page_size: 12 }), [])
  const topics = useApi(() => api.topics(), [])
  const target = id || (scope === 'product' ? risky.data?.items?.[0]?.product_id : String(topics.data?.topics?.[0]?.topic_id ?? ''))

  const run = async (refresh = false) => {
    setRes({ loading: true })
    try { setRes({ data: await api.aiInsights({ scope, id: target, refresh }) }) } catch (e) { setRes({ error: errorMessage(e) }) }
    app.refreshHealth()
  }

  return (
    <div className="space-y-5">
      <GeminiStatus h={h} />
      <div className="grid xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-5 items-start">
        <Card title="Phân tích nguyên nhân – giải pháp" subtitle="Gửi tối đa 30 đánh giá tiêu cực của một sản phẩm hoặc một chủ đề; kết quả được lưu lại cho lần xem sau">
          <div className="flex flex-wrap items-end gap-3">
            <div><div className="text-[12px] text-muted mb-1">Phân tích theo</div><Segmented value={scope} onChange={(v) => { setScope(v); setId(''); setRes({}) }} options={[['product', 'Sản phẩm'], ['topic', 'Chủ đề phàn nàn']]} /></div>
            {scope === 'product' ? (
              <label className="flex flex-col gap-1 text-[12px] text-muted">Mã sản phẩm
                <input className="input w-48 font-mono" value={id} placeholder={risky.data?.items?.[0]?.product_id || 'B00…'} onChange={(e) => setId(e.target.value.toUpperCase().trim())} />
              </label>
            ) : (
              <label className="flex flex-col gap-1 text-[12px] text-muted">Chủ đề
                <select className="input w-72" value={target} onChange={(e) => setId(e.target.value)}>
                  {(topics.data?.topics || []).map((t) => <option key={t.topic_id} value={t.topic_id}>{t.name} ({pct(t.share, 0)})</option>)}
                </select>
              </label>
            )}
            <button className="btn btn-ai" disabled={res.loading || !target} onClick={() => run(false)}>{res.loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}Phân tích</button>
            {res.data && <button className="btn" disabled={res.loading} onClick={() => run(true)}>Gọi lại, bỏ qua kết quả đã lưu</button>}
          </div>
          {scope === 'product' && (
            <div className="mt-3">
              <div className="text-[12px] text-muted mb-1.5">Sản phẩm rủi ro cao – chọn nhanh</div>
              <div className="flex flex-wrap gap-1.5">
                {(risky.data?.items || []).map((p) => (
                  <button key={p.product_id} onClick={() => { setId(p.product_id); setRes({}) }} className={`chip font-mono ${target === p.product_id ? '!border-ai !text-ai bg-aiSoft' : ''}`}>{p.product_id}</button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-5">
            {res.error && <ErrorBox error={res.error} />}
            {res.loading && <Loading h="h-40" label="Trợ lý AI đang đọc đánh giá và tìm nguyên nhân…" />}
            {res.data && (
              <>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <div className="text-[15px] font-semibold text-ink flex-1">{res.data.title}</div>
                  {scope === 'product' && <button className="btn" onClick={() => app.openProduct(res.data.id)}>Chi tiết sản phẩm</button>}
                </div>
                {res.data.stats && <div className="text-[12.5px] text-muted mb-3 leading-relaxed">Số liệu gửi kèm: {res.data.stats}</div>}
                <InsightView data={res.data} />
              </>
            )}
            {!res.loading && !res.data && !res.error && (
              <div className="text-[13px] text-muted leading-relaxed">
                Chọn một sản phẩm hoặc chủ đề rồi bấm “Phân tích”. Kết quả gồm tối đa 5 nguyên nhân sắp theo mức nghiêm trọng; mỗi nguyên nhân phải trích
                review_id có trong dữ liệu (backend kiểm tra và loại nguyên nhân không có bằng chứng), kèm 1 hành động, mức ưu tiên và chỉ số theo dõi.
              </div>
            )}
          </div>
        </Card>
        <div>
          <Chatbot embedded prefill={app.chat?.prefill} nonce={app.chat?.nonce} />
          <div className="text-[12px] text-muted mt-2 leading-relaxed">
            Trợ lý tự chọn công cụ để đọc dữ liệu: KPI tổng quan, bảng cảnh báo, xếp hạng sản phẩm, chi tiết sản phẩm, chủ đề phàn nàn, chuỗi theo tháng,
            dự báo, mô hình dự đoán, tìm kiếm đánh giá, chỉ số mô hình. Câu hỏi ngoài hệ thống được trả lời bằng kiến thức chung của Gemini.
          </div>
        </div>
      </div>
    </div>
  )
}

function GeminiStatus({ h }) {
  if (h?.gemini_configured && !h?.gemini_error) return (
    <Note tone="ai" icon={Sparkles}>Đã cấu hình khóa Gemini{h.gemini_model ? <> – đang dùng <b>{h.gemini_model}</b></> : ' – model sẽ được chọn tự động ở lần gọi đầu tiên'}. Khóa chỉ nằm ở backend (backend/.env), không gửi xuống trình duyệt.</Note>
  )
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900 flex items-start gap-3">
      <KeyRound size={18} className="mt-0.5 shrink-0" />
      <div className="flex-1 leading-relaxed">
        {h?.gemini_error ? <><b>Gemini đang lỗi:</b> {h.gemini_error}.</> : <><b>Chưa có khóa Gemini.</b> Trợ lý vẫn trả lời câu hỏi về dữ liệu bằng quy tắc, phân tích nguyên nhân dùng chủ đề NMF.</>}
        {' '}Để bật Gemini: mở <code className="bg-white/70 px-1 rounded">backend/.env</code>, điền <code className="bg-white/70 px-1 rounded">GEMINI_API_KEY=khóa_của_bạn</code>, lưu file rồi khởi động lại backend.
        Hỗ trợ khóa Google AI Studio (AIza…) và khóa Vertex AI (AQ.…).
      </div>
    </div>
  )
}
