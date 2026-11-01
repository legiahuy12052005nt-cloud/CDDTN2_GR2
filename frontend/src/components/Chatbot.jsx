import { useEffect, useRef, useState } from 'react'
import { Bot, Database, Eraser, Loader2, MessageCircle, SendHorizontal, Sparkles, X } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { chatStore, useChat } from '../lib/chatStore.js'
import Markdown from './Markdown.jsx'

const SUGGEST_DATA = [
  'Tổng quan dữ liệu và mức độ hài lòng hiện tại thế nào?',
  'Những sản phẩm nào đang rủi ro cao và vì sao?',
  'Khách phàn nàn nhiều nhất về chủ đề gì? Nên xử lý ra sao?',
  'Dự báo chỉ số hài lòng 6 tháng tới',
  'Dự đoán giúp: "The coffee was stale and tasted burnt, box arrived crushed"',
  'Có bao nhiêu đánh giá nhắc tới "expired" và điểm trung bình của chúng?',
]
const SUGGEST_GENERAL = ['Cách viết phản hồi xin lỗi khách khi giao hàng hết hạn?', 'Giải thích F1-macro dễ hiểu']

export default function Chatbot({ open, onOpenChange, prefill, nonce, embedded = false }) {
  const app = useApp()
  const { messages, pending } = useChat()
  const [text, setText] = useState('')
  const end = useRef(null)
  const ta = useRef(null)

  // câu hỏi gợi sẵn chỉ điền khi có lần bấm “Hỏi trợ lý” mới (nonce đổi sau khi khung chat đã hiện);
  // đóng rồi mở lại, hoặc chuyển tab làm khung chat hiện lại, không điền lại câu đã gửi
  const seen = useRef(nonce)
  useEffect(() => { if (nonce !== seen.current) { seen.current = nonce; if (prefill) setText(prefill) } }, [nonce]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (open || embedded) setTimeout(() => ta.current?.focus(), 50) }, [nonce, open, embedded])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages.length, pending, open])

  const send = async (msg) => {
    const m = (msg ?? text).trim()
    if (!m || pending) return
    setText('')
    const history = chatStore.get().messages.slice(-10).map(({ role, content }) => ({ role, content }))
    chatStore.push({ role: 'user', content: m })
    chatStore.setPending(true)
    try {
      const r = await api.chat({ message: m, history, context: { page: app?.pageLabel, product_id: app?.product || undefined } })
      chatStore.push({ role: 'assistant', content: r.answer, data_used: r.data_used, source: r.source, model: r.model, ms: r.latency_ms })
    } catch (e) {
      chatStore.push({ role: 'assistant', content: `**Không gửi được câu hỏi:** ${errorMessage(e)}`, error: true })
    } finally { chatStore.setPending(false) }
  }

  const h = app?.health
  const status = h?.gemini_configured ? (h?.gemini_error ? `Gemini lỗi gần nhất: ${h.gemini_error}` : `Gemini${h?.gemini_model ? ` · ${h.gemini_model}` : ''} · đọc dữ liệu hệ thống qua 10 công cụ`) : 'Chưa có khóa Gemini · trả lời theo quy tắc từ dữ liệu hệ thống'

  const panel = (
    <div className={`flex flex-col bg-white ${embedded ? 'h-[640px] rounded-xl border border-line shadow-card' : 'h-full'}`}>
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-line">
        <span className="w-8 h-8 rounded-full bg-ai text-white flex items-center justify-center"><Bot size={17} /></span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-ink text-[14px]">Trợ lý FoodReview</div>
          <div className="text-[11.5px] text-muted truncate" title={status}>{status}</div>
        </div>
        {messages.length > 0 && <button className="btn btn-ghost h-8 px-2" title="Xóa hội thoại" onClick={chatStore.clear}><Eraser size={15} /></button>}
        {!embedded && <button className="btn btn-ghost h-8 px-2" aria-label="Đóng" onClick={() => onOpenChange(false)}><X size={16} /></button>}
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-slate-50/50">
        {messages.length === 0 && (
          <div className="text-[13px] text-text">
            <p className="leading-relaxed">Hỏi về dữ liệu đánh giá, sản phẩm, chủ đề phàn nàn, dự báo – trợ lý tự tra số liệu trong hệ thống để trả lời. Câu hỏi kiến thức chung cũng được.</p>
            {app?.product && <p className="mt-2 text-[12.5px] text-muted">Đang chọn sản phẩm <b className="font-mono">{app.product}</b> – có thể hỏi “sản phẩm này thế nào?”.</p>}
            <div className="mt-3 flex flex-col gap-1.5">
              {SUGGEST_DATA.map((s) => <button key={s} className="text-left rounded-lg border border-line bg-white px-3 py-2 hover:border-ai/50 hover:text-ai" onClick={() => send(s)}>{s}</button>)}
            </div>
            <div className="mt-3 text-[12px] text-muted">Ngoài hệ thống</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {SUGGEST_GENERAL.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {messages.map((m, i) => m.role === 'user' ? (
          <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-ai text-white px-3.5 py-2 text-[13.5px] whitespace-pre-wrap">{m.content}</div></div>
        ) : (
          <div key={i} className="flex gap-2">
            <span className="w-6 h-6 shrink-0 rounded-full bg-aiSoft text-ai flex items-center justify-center mt-0.5"><Sparkles size={13} /></span>
            <div className={`max-w-[92%] rounded-2xl rounded-tl-md border px-3.5 py-2 ${m.error ? 'bg-red-50 border-red-200' : 'bg-white border-line'}`}>
              <Markdown>{m.content}</Markdown>
              {(m.data_used?.length > 0 || m.source) && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2 pt-2 border-t border-slate-100 text-[11.5px] text-muted">
                  {m.data_used?.length > 0 && <><Database size={12} />{m.data_used.map((d) => <span key={d} className="rounded bg-slate-100 px-1.5 py-0.5">{d}</span>)}</>}
                  <span className="ml-auto">{m.source === 'gemini' ? `Gemini${m.model ? ` · ${m.model}` : ''}` : m.source === 'rule' ? 'Quy tắc' : ''}{m.ms ? ` · ${(m.ms / 1000).toFixed(1).replace('.', ',')} s` : ''}</span>
                </div>
              )}
            </div>
          </div>
        ))}
        {pending && <div className="flex items-center gap-2 text-[13px] text-muted pl-8"><Loader2 size={14} className="animate-spin" />Đang tra dữ liệu và soạn câu trả lời…</div>}
        <div ref={end} />
      </div>
      <form className="p-3 border-t border-line flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); send() }}>
        <textarea ref={ta} rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder="Nhập câu hỏi… (Enter để gửi)" title="Enter để gửi, Shift+Enter để xuống dòng"
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          className="flex-1 resize-none max-h-32 min-h-[38px] rounded-lg border border-line px-3 py-2 text-[13.5px] focus:outline-none focus:ring-2 focus:ring-ai/30" />
        <button type="submit" className="btn btn-ai h-[38px] w-[38px] px-0" disabled={pending || !text.trim()} aria-label="Gửi"><SendHorizontal size={16} /></button>
      </form>
    </div>
  )

  if (embedded) return panel
  return (
    <>
      {!open && (
        // nút tròn gọn ở góc để không che bảng, biểu đồ; rê chuột (hoặc focus bằng bàn phím) mới hiện chữ
        <button onClick={() => onOpenChange(true)} aria-label="Hỏi trợ lý AI" title="Hỏi trợ lý AI"
          className="group fixed bottom-5 right-1 z-40 flex items-center rounded-full bg-ai text-white h-10 min-w-10 px-[11px] shadow-lg ring-2 ring-white hover:bg-[#4e3dc4] focus-visible:outline-none">
          <MessageCircle size={18} className="shrink-0" />
          <span className="max-w-0 overflow-hidden whitespace-nowrap text-[13.5px] font-medium transition-all duration-200 group-hover:max-w-[120px] group-hover:ml-2 group-focus-visible:max-w-[120px] group-focus-visible:ml-2">Hỏi trợ lý AI</span>
        </button>
      )}
      {open && (
        <div className="fixed z-50 bottom-5 right-5 w-[min(440px,calc(100vw-2.5rem))] h-[min(680px,calc(100vh-2.5rem))] rounded-2xl overflow-hidden border border-line shadow-2xl">
          {panel}
        </div>
      )}
    </>
  )
}
