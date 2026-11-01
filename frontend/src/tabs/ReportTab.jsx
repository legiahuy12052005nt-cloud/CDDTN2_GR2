import { useState } from 'react'
import toast from 'react-hot-toast'
import { Download, FileSpreadsheet, FileText, Loader2, RefreshCcw, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { nf } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Card, Note } from '../components/ui.jsx'

const CSV = [
  ['product_risk', 'Cảnh báo sản phẩm', 'Mọi sản phẩm: mức rủi ro, lý do, điểm 3 tháng, tỷ lệ tiêu cực, điều kiện dự báo'],
  ['topics', 'Chủ đề phàn nàn', 'Tên chủ đề, tỷ trọng, 10 từ khóa, gợi ý hành động'],
  ['predictions', 'Dự đoán tập kiểm tra', 'Số sao thật/dự đoán, xác suất 5 mức, cờ đánh giá mâu thuẫn'],
  ['monthly', 'Chuỗi theo tháng', 'Số đánh giá, điểm TB, tỷ lệ tiêu cực, chỉ số hài lòng theo tháng'],
  ['forecast', 'Dự báo chỉ số hài lòng', '12 tháng tới: chỉ số dự báo, khoảng tin cậy 95%, mô hình dùng'],
  ['model_metrics', 'Chỉ số mô hình', 'F1-macro, F1 từng lớp, accuracy, MAE của 4 mô hình; kèm kết quả kiểm tra theo thời gian'],
]

export default function ReportTab() {
  const app = useApp()
  const m = useApi(() => api.modelMetrics(), [])
  const [pdf, setPdf] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const ds = app.health?.dataset || {}

  const downloadPdf = async () => {
    setPdf(true)
    try {
      const r = await fetch(api.reportPdfUrl())
      if (!r.ok) throw new Error((await r.json()).error?.message || 'Không tạo được PDF')
      const blob = await r.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `bao_cao_foodreview_${ds.dataset_version}.pdf`; a.click(); URL.revokeObjectURL(url)
      toast.success('Đã tạo báo cáo PDF')
    } catch (e) { toast.error(errorMessage(e)) } finally { setPdf(false) }
  }
  const reset = async () => {
    try { await api.reset(); toast.success('Đã xóa phiên làm việc'); window.location.reload() } catch (e) { toast.error(errorMessage(e)) }
  }

  return (
    <div className="grid xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-5 items-start">
      <div className="space-y-5">
        <Card title="Báo cáo PDF tiếng Việt" subtitle="Tạo từ dữ liệu hiện tại: chỉ số tổng quan, phân bố số sao, chỉ số hài lòng và dự báo, so sánh mô hình, danh sách sản phẩm rủi ro, chủ đề phàn nàn kèm gợi ý, các phân tích AI đã lưu">
          <div className="flex items-center gap-4 rounded-xl bg-slate-50 p-4">
            <div className="w-12 h-14 rounded-md bg-white border border-line flex items-center justify-center text-neg"><FileText size={24} /></div>
            <div className="flex-1">
              <div className="font-medium text-ink">bao_cao_foodreview_{ds.dataset_version}.pdf</div>
              <div className="text-[12.5px] text-muted">Khổ A4 · khoảng 3–4 trang · tạo trong vài giây</div>
            </div>
            <button className="btn btn-primary" disabled={pdf} onClick={downloadPdf}>{pdf ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}Tạo và tải PDF</button>
          </div>
        </Card>
        <Card title="Bảng kết quả CSV" subtitle="Mã hóa UTF-8 có BOM để mở đúng tiếng Việt trong Excel">
          <div className="divide-y divide-slate-100">
            {CSV.map(([k, t, d]) => (
              <div key={k} className="flex items-center gap-4 py-3">
                <FileSpreadsheet size={20} className="text-emerald-700 shrink-0" />
                <div className="flex-1"><div className="font-medium text-ink text-[13.5px]">{t}</div><div className="text-[12.5px] text-muted">{d}</div></div>
                <a className="btn" href={api.exportUrl(k)}><Download size={14} />CSV</a>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <div className="space-y-5">
        <Card title="Phiên dữ liệu hiện tại">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
            <dt className="text-muted">File</dt><dd className="text-ink">{ds.file_name}</dd>
            <dt className="text-muted">Phiên bản</dt><dd className="text-ink font-mono">{ds.dataset_version}</dd>
            <dt className="text-muted">Đánh giá sạch</dt><dd className="text-ink">{nf(ds.n_reviews)}</dd>
            <dt className="text-muted">Sản phẩm</dt><dd className="text-ink">{nf(ds.n_products)}</dd>
            <dt className="text-muted">Thời gian</dt><dd className="text-ink">{ds.date_min} → {ds.date_max}</dd>
            <dt className="text-muted">Xử lý lúc</dt><dd className="text-ink">{ds.created_at?.replace('T', ' ')}</dd>
            <dt className="text-muted">Mô hình</dt><dd className="text-ink">{m.data ? `${m.data.selected} · F1-macro ${nf(m.data.models.find((x) => x.selected)?.f1_macro3, 3)}` : '…'}</dd>
          </dl>
          <div className="mt-4" /><Note>Kết quả được lưu trên máy chủ (data/processed, models, cache) nên tắt và mở lại ứng dụng không mất dữ liệu.</Note>
        </Card>
        <Card title="Đổi dữ liệu hoặc xóa phiên" subtitle="Tải file mới sẽ thay toàn bộ kết quả; xóa phiên đưa ứng dụng về trạng thái ban đầu">
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={app.changeData}><RefreshCcw size={14} />Tải file khác</button>
            {!confirm ? <button className="btn text-neg" onClick={() => setConfirm(true)}><Trash2 size={14} />Xóa phiên làm việc</button>
              : <><button className="btn !border-neg !bg-neg text-white" onClick={reset}>Xác nhận xóa toàn bộ kết quả</button><button className="btn" onClick={() => setConfirm(false)}>Hủy</button></>}
          </div>
        </Card>
      </div>
    </div>
  )
}
