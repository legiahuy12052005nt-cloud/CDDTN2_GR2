import { useCallback, useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from './api/client.js'
import UploadPage from './pages/UploadPage.jsx'
import Dashboard from './pages/Dashboard.jsx'

// Luồng chính (báo cáo buổi 4, hình 4.3): Trang tải dữ liệu → Dashboard 9 tab.
// Khi mở lại trình duyệt, nếu backend đã có dữ liệu và mô hình (nạp lại từ đĩa) thì vào thẳng Dashboard.
export default function App() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('loading')

  const refresh = useCallback(() => api.health().then((h) => { setHealth(h); setError(null); return h }).catch((e) => { setError(errorMessage(e)); throw e }), [])

  useEffect(() => {
    refresh().then((h) => setView(h.dataset_loaded && h.model_ready && !h.job_running ? 'dashboard' : 'upload')).catch(() => setView('offline'))
  }, [refresh])

  if (view === 'loading') return <div className="h-screen flex items-center justify-center text-muted gap-2"><Loader2 className="animate-spin" size={18} />Đang kết nối máy chủ…</div>
  if (view === 'offline') return (
    <div className="h-screen flex items-center justify-center p-6">
      <div className="max-w-md text-center">
        <h1 className="text-lg font-semibold text-ink">Chưa kết nối được backend</h1>
        <p className="text-sm text-muted mt-2">{error}</p>
        <p className="text-[13px] text-muted mt-3">Chạy <code className="bg-slate-100 px-1 rounded">uvicorn backend.main:app --port 8000</code> ở thư mục gốc dự án rồi tải lại trang.</p>
        <button className="btn btn-primary mt-4" onClick={() => refresh().then((h) => setView(h.dataset_loaded && h.model_ready && !h.job_running ? 'dashboard' : 'upload')).catch(() => {})}>Thử kết nối lại</button>
      </div>
    </div>
  )
  return view === 'dashboard'
    ? <Dashboard health={health} refreshHealth={refresh} onChangeData={() => setView('upload')} />
    : <UploadPage health={health} refreshHealth={refresh} onDone={() => refresh().then(() => setView('dashboard'))} onBack={health?.dataset_loaded ? () => setView('dashboard') : null} />
}
