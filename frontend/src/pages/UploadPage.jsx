import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { ArrowLeft, CheckCircle2, CircleDashed, Database, FileUp, Loader2, Sparkles, XCircle } from 'lucide-react'
import { api, errorMessage } from '../api/client.js'
import { nf } from '../lib/format.js'
import { BrandMark } from '../components/Brand.jsx'

const STEP_HINT = {
  validate: 'Đủ cột Score, Time, Text; kiểu dữ liệu đúng',
  clean: 'Bỏ trùng, bỏ HTML/URL, ẩn danh UserId, chuẩn hóa văn bản',
  eda: 'Phân bố số sao, xu hướng tháng, từ khóa đặc trưng',
  train_model: 'Naive Bayes, Linear SVM, Logistic Regression; kiểm tra lại LR khi học trên dữ liệu cũ, dự đoán năm cuối',
  topics: 'NMF trên đánh giá 1–2 sao, đặt tên chủ đề',
  forecast: 'ETS trên chỉ số hài lòng theo tháng, kiểm tra lùi 12 tháng',
  alerts: 'So sánh 3 tháng gần nhất với 3 tháng trước cho từng sản phẩm; kiểm tra ngược quy tắc',
}

export default function UploadPage({ health, refreshHealth, onDone, onBack }) {
  const [drag, setDrag] = useState(false)
  const [uploadPct, setUploadPct] = useState(null)
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const input = useRef(null)
  const timer = useRef(null)

  const poll = (jobId) => {
    clearInterval(timer.current)
    const t0 = Date.now()
    timer.current = setInterval(async () => {
      setElapsed(Math.round((Date.now() - t0) / 1000))
      try {
        const j = await api.job(jobId); setJob(j)
        if (j.status === 'done' || j.status === 'failed') {
          clearInterval(timer.current)
          // thất bại cũng cập nhật trạng thái: nút “Về dashboard” chỉ hiện khi máy chủ còn dữ liệu dùng được
          if (j.status === 'done') toast.success('Đã xử lý xong dữ liệu')
          refreshHealth().catch(() => {})
        }
      } catch (e) { clearInterval(timer.current); setErr(errorMessage(e)) }
    }, 1000)
  }
  useEffect(() => {
    if (health?.job_running) { setBusy(true); poll(health.job_running) }
    return () => clearInterval(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const start = async (promise) => {
    setErr(null); setBusy(true); setJob(null)
    try {
      const acc = await promise
      setUploadPct(null)
      setJob({ status: 'queued', progress: 0, steps: [], file_name: acc.file_name, n_rows_raw: acc.n_rows_raw })
      poll(acc.job_id)
    } catch (e) { setErr(errorMessage(e)); setBusy(false); setUploadPct(null) }
  }
  const onFile = (f) => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) { setErr('Chỉ nhận file .csv'); return }
    setUploadPct(0)
    start(api.upload(f, setUploadPct))
  }

  const running = busy && (!job || ['queued', 'running'].includes(job.status))
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-ink text-white">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-3">
          <BrandMark />
          <div className="font-semibold tracking-tight">FoodReview Insight</div>
          <div className="flex-1" />
          {onBack && !running && <button className="btn btn-ghost text-white hover:bg-white/10" onClick={onBack}><ArrowLeft size={15} />Về dashboard</button>}
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-10 grid lg:grid-cols-[1fr_1.15fr] gap-10 items-start">
        <section className="pt-2">
          <h1 className="text-[30px] leading-[1.15] font-semibold text-ink tracking-tight">Biết khách đang không hài lòng điều gì, trước khi điểm sao tụt xuống</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-text max-w-[52ch]">
            Tải file đánh giá thực phẩm (định dạng Amazon Fine Food Reviews). Hệ thống làm sạch dữ liệu, huấn luyện mô hình dự đoán cảm xúc,
            tìm chủ đề phàn nàn, dự báo chỉ số hài lòng và gắn cảnh báo cho từng sản phẩm.
          </p>
          <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 max-w-lg">
            {[['Cảm xúc', 'Dự đoán số sao và cảm xúc cho đánh giá mới, giải thích bằng từ khóa'],
              ['Chủ đề phàn nàn', 'Nhóm đánh giá 1–2 sao thành vấn đề cụ thể kèm gợi ý xử lý'],
              ['Dự báo', 'Chỉ số hài lòng 3, 6, 12 tháng tới với khoảng tin cậy'],
              ['Cảnh báo sớm', 'Sản phẩm có điểm 3 tháng gần nhất giảm hoặc tỷ lệ tiêu cực cao']].map(([t, d]) => (
              <div key={t}><dt className="text-[14px] font-semibold text-ink">{t}</dt><dd className="text-[13px] text-muted mt-1 leading-snug">{d}</dd></div>
            ))}
          </dl>
        </section>

        <section className="bg-white rounded-2xl border border-line shadow-card p-6">
          {!running && job?.status !== 'done' && (
            <>
              <h2 className="text-[16px] font-semibold text-ink">Chọn dữ liệu</h2>
              <div
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); onFile(e.dataTransfer.files[0]) }}
                onClick={() => input.current?.click()} role="button" tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && input.current?.click()}
                className={`mt-4 rounded-xl border-2 border-dashed px-6 py-9 text-center cursor-pointer transition-colors ${drag ? 'border-primary bg-primarySoft' : 'border-slate-300 hover:border-primary/60 hover:bg-slate-50'}`}>
                <FileUp className="mx-auto text-primary" size={30} />
                <div className="mt-2 font-medium text-ink">Kéo thả file .csv vào đây hoặc bấm để chọn</div>
                <div className="text-[12.5px] text-muted mt-1">Tối đa 400 MB · cần cột Score, Time, Text · nên có ProductId, UserId, Summary</div>
                <input ref={input} type="file" accept=".csv" className="hidden" onChange={(e) => onFile(e.target.files[0])} />
              </div>
              <div className="flex items-center gap-3 my-5 text-[12px] text-muted"><span className="h-px flex-1 bg-line" />hoặc dùng dữ liệu có sẵn trên máy chủ<span className="h-px flex-1 bg-line" /></div>
              <div className="grid sm:grid-cols-2 gap-3">
                <button className="text-left rounded-xl border border-line px-4 py-3 hover:border-primary/60 hover:bg-primarySoft/40 disabled:opacity-50"
                  disabled={!health?.sample_available} onClick={() => start(api.useSample('sample'))}>
                  <div className="flex items-center gap-2 font-medium text-ink"><Sparkles size={15} className="text-primary" />Mẫu 100.000 đánh giá</div>
                  <div className="text-[12.5px] text-muted mt-1">Mẫu phân tầng theo số sao, xử lý khoảng 2–3 phút</div>
                </button>
                <button className="text-left rounded-xl border border-line px-4 py-3 hover:border-primary/60 hover:bg-primarySoft/40 disabled:opacity-50"
                  disabled={!health?.raw_available} onClick={() => start(api.useSample('full'))}
                  title={health?.raw_available ? '' : 'Đặt Reviews.csv vào backend/data/raw để dùng'}>
                  <div className="flex items-center gap-2 font-medium text-ink"><Database size={15} className="text-primary" />Toàn bộ Reviews.csv</div>
                  <div className="text-[12.5px] text-muted mt-1">{health?.raw_available ? '568.454 dòng, xử lý khoảng 3–4 phút' : 'Chưa có file trong data/raw'}</div>
                </button>
              </div>
              {err && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-800">{err}</div>}
              {job?.status === 'failed' && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[13px] text-red-800">
                  Xử lý thất bại: {job.error?.message}. Hãy kiểm tra file rồi thử lại.
                </div>
              )}
              {health?.dataset_loaded && <p className="text-[12.5px] text-muted mt-4">Đang có dữ liệu “{health.dataset?.file_name}”. Tải file mới sẽ thay thế toàn bộ kết quả hiện tại.</p>}
            </>
          )}

          {(running || job?.status === 'done') && (
            <Progress job={job} uploadPct={uploadPct} elapsed={elapsed} onDone={onDone} />
          )}
        </section>
      </main>
    </div>
  )
}

function Progress({ job, uploadPct, elapsed, onDone }) {
  const steps = job?.steps?.length ? job.steps : Object.keys(STEP_HINT).map((n) => ({ name: n, status: 'pending' }))
  const s = job?.summary
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <h2 className="text-[16px] font-semibold text-ink flex-1">{job?.status === 'done' ? 'Đã xử lý xong' : uploadPct != null ? 'Đang tải file lên' : 'Đang xử lý dữ liệu'}</h2>
        <span className="text-[12.5px] text-muted tabular-nums">{elapsed ? `${elapsed} giây` : ''}</span>
      </div>
      <div className="text-[13px] text-muted mt-0.5">{job?.file_name}{job?.n_rows_raw ? ` · ${nf(job.n_rows_raw)} dòng` : ''}</div>
      <div className="mt-4 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${uploadPct != null ? uploadPct : job?.progress || 0}%` }} />
      </div>
      <ol className="mt-5 space-y-2.5">
        {steps.map((st) => (
          <li key={st.name} className="flex items-start gap-3">
            <span className="mt-0.5">
              {st.status === 'done' ? <CheckCircle2 size={18} className="text-emerald-600" />
                : st.status === 'running' ? <Loader2 size={18} className="text-primary animate-spin" />
                  : st.status === 'failed' ? <XCircle size={18} className="text-red-600" /> : <CircleDashed size={18} className="text-slate-300" />}
            </span>
            <div className="flex-1 min-w-0">
              <div className={`text-[13.5px] ${st.status === 'pending' ? 'text-muted' : 'text-ink font-medium'}`}>{st.label || st.name}</div>
              <div className="text-[12px] text-muted">{st.status === 'running' && job?.message ? job.message : STEP_HINT[st.name]}</div>
            </div>
            {st.seconds != null && <span className="text-[12px] text-muted tabular-nums">{nf(st.seconds, 1)} s</span>}
          </li>
        ))}
      </ol>
      {s && (
        <div className="mt-6 rounded-xl bg-slate-50 border border-line p-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div><div className="text-[20px] font-semibold text-ink tabular-nums">{nf(s.n_clean)}</div><div className="text-[12px] text-muted">đánh giá sạch / {nf(s.n_raw)}</div></div>
            <div><div className="text-[20px] font-semibold text-ink tabular-nums">{nf(s.f1_macro3, 3)}</div><div className="text-[12px] text-muted">F1-macro ({s.selected_model})</div></div>
            <div><div className="text-[20px] font-semibold tabular-nums" style={{ color: '#d03b3b' }}>{nf(s.n_high_risk)}</div><div className="text-[12px] text-muted">sản phẩm rủi ro cao</div></div>
          </div>
          <button className="btn btn-primary w-full mt-4 h-10" onClick={onDone}>Mở dashboard</button>
        </div>
      )}
    </div>
  )
}
