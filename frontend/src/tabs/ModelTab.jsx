import { useState } from 'react'
import { Bar as RBar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CheckCircle2 } from 'lucide-react'
import { api } from '../api/client.js'
import { useApp } from '../lib/appContext.js'
import { COLOR, SENT, nf, pct } from '../lib/format.js'
import useApi from '../lib/useApi.js'
import { Card, ChartTip, ErrorBox, Loading, Pager, Segmented, SentBadge, Stars, axisProps } from '../components/ui.jsx'

const NAME = { LR: 'Logistic Regression', NB: 'Multinomial Naive Bayes', SVM: 'Linear SVM (hiệu chỉnh xác suất)', B0: 'Đường cơ sở: luôn 5 sao' }

export default function ModelTab() {
  const m = useApi(() => api.modelMetrics(), [])
  const kw = useApi(() => api.modelKeywords(20), [])
  const [cm, setCm] = useState(3)
  if (m.loading) return <Loading h="h-80" />
  if (m.error) return <ErrorBox error={m.error} onRetry={m.reload} />
  const d = m.data
  const sel = d.models.find((x) => x.selected)
  const sp = d.split
  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)] gap-5">
        <Card title="Mô hình đang dùng để dự đoán">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-primarySoft text-primary flex items-center justify-center"><CheckCircle2 size={24} /></div>
            <div className="flex-1">
              <div className="text-[18px] font-semibold text-ink">{NAME[sel.model]}</div>
              <div className="text-[13px] text-muted">{sel.params} · huấn luyện lúc {d.trained_at?.replace('T', ' ')}</div>
              <div className="flex gap-6 mt-3">
                <Big v={nf(sel.f1_macro3, 3)} l="F1-macro 3 lớp" />
                <Big v={nf(sel.f1_neg, 3)} l="F1 lớp tiêu cực" />
                <Big v={pct(sel.acc5)} l="Đúng chính xác số sao" />
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-[13px] leading-relaxed text-text">
            Học từ <b className="text-ink">{nf(sp.train)}</b> đánh giá đã làm sạch, kiểm tra trên <b className="text-ink">{nf(sp.test)}</b> đánh giá chưa từng thấy
            (chia 80/20 phân tầng theo số sao, random_state = {sp.random_state}){sp.sampled ? `; lấy mẫu phân tầng ${nf(sp.n_used)} trong ${nf(sp.n_dataset)} đánh giá để huấn luyện nhanh` : ''}.
            Văn bản = tiêu đề + nội dung, chuyển chữ thường, tách “n't” → “not”, vector TF-IDF 1–2-gram ({nf(d.vectorizer?.n_features)} đặc trưng).
            Logistic Regression là cấu hình đã chọn trên tập validation ở thực nghiệm (F1-macro 3 lớp cao nhất – thước đo chính vì dữ liệu lệch mạnh về 5 sao)
            và có hệ số để giải thích từ khóa; tập kiểm tra ở đây chỉ dùng để báo cáo, không dùng để chọn lại mô hình.
          </div>
        </Card>
        <Card title="So sánh các mô hình trên tập kiểm tra" subtitle="F1-macro 3 lớp (tiêu cực / trung tính / tích cực) – thước đo chính, đo trên tập kiểm tra">
          <div className="h-48">
            <ResponsiveContainer>
              <BarChart data={d.models} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 0 }}>
                <XAxis type="number" domain={[0, 1]} hide />
                <YAxis type="category" dataKey="model" {...axisProps} width={44} />
                <Tooltip cursor={{ fill: '#f1f5f9' }} content={<ChartTip labelFormat={(k) => NAME[k]} rows={(x) => [['F1-macro', nf(x.f1_macro3, 3), x.selected ? COLOR.primary : COLOR.axis], ['Accuracy 5 sao', pct(x.acc5)], ['Thời gian học', `${nf(x.fit_seconds, 1)} s`]]} />} />
                <RBar dataKey="f1_macro3" barSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
                  {d.models.map((x) => <Cell key={x.model} fill={x.selected ? COLOR.primary : x.model === 'B0' ? '#dfe4ea' : '#b8c2cd'} />)}
                  <LabelList dataKey="f1_macro3" position="right" formatter={(v) => nf(v, 3)} style={{ fontSize: 12, fill: COLOR.text }} />
                </RBar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="Bảng chỉ số chi tiết" pad={false}>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr><th>Mô hình</th><th>Tham số</th><th className="text-right">F1-macro</th><th className="text-right">F1 tiêu cực</th><th className="text-right">F1 trung tính</th><th className="text-right">F1 tích cực</th><th className="text-right">Precision / Recall tiêu cực</th><th className="text-right">Accuracy 3 lớp</th><th className="text-right">Accuracy 5 sao</th><th className="text-right">MAE (sao)</th><th className="text-right">Thời gian học</th></tr></thead>
            <tbody>{d.models.map((x) => (
              <tr key={x.model} className={x.selected ? 'bg-primarySoft/50' : ''}>
                <td className="text-ink font-medium whitespace-nowrap">{x.selected && <CheckCircle2 size={13} className="inline text-primary mr-1 -mt-0.5" />}{NAME[x.model]}</td>
                <td className="text-muted whitespace-nowrap">{x.params}</td>
                <td className="text-right font-semibold text-ink">{nf(x.f1_macro3, 3)}</td><td className="text-right">{nf(x.f1_neg, 3)}</td><td className="text-right">{nf(x.f1_neu, 3)}</td><td className="text-right">{nf(x.f1_pos, 3)}</td>
                <td className="text-right">{nf(x.prec_neg, 3)} / {nf(x.rec_neg, 3)}</td><td className="text-right">{pct(x.acc3)}</td><td className="text-right">{pct(x.acc5)}</td><td className="text-right">{nf(x.mae, 3)}</td><td className="text-right">{nf(x.fit_seconds, 1)} s</td>
              </tr>))}</tbody>
          </table>
        </div>
        <div className="px-5 py-3 text-[12px] text-muted">Lớp trung tính (3 sao) khó nhất vì nội dung thường vừa khen vừa chê; đường cơ sở “luôn 5 sao” đạt accuracy cao nhưng F1-macro thấp – lý do không dùng accuracy để chọn mô hình.</div>
      </Card>

      <Reliability tc={d.time_check} ref_={d.reference} sel={sel} sp={sp} />

      <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-5">
        <Card title="Ma trận nhầm lẫn" subtitle="Hàng: nhãn thật · cột: dự đoán · màu theo tỷ lệ trong hàng" action={<Segmented value={cm} onChange={setCm} options={[[3, '3 lớp'], [5, '5 sao']]} />}>
          <Confusion m={cm === 3 ? d.confusion3 : d.confusion5} labels={cm === 3 ? ['Tiêu cực', 'Trung tính', 'Tích cực'] : ['1★', '2★', '3★', '4★', '5★']} />
        </Card>
        <Card title="Từ khóa ảnh hưởng đến số sao" subtitle="Trọng số w = Σ (k − 3)·β_k từ hệ số Logistic Regression: dương kéo số sao lên, âm kéo xuống">
          {kw.loading ? <Loading /> : kw.data && (
            <div className="grid sm:grid-cols-2 gap-6">
              <KwList items={kw.data.down} color={COLOR.neg} title="Kéo số sao xuống" />
              <KwList items={kw.data.up} color={COLOR.pos} title="Kéo số sao lên" />
            </div>
          )}
        </Card>
      </div>
      <Mismatch n={d.n_mismatch} />
    </div>
  )
}

function Big({ v, l }) { return <div><div className="text-[22px] font-semibold text-ink tabular-nums leading-tight">{v}</div><div className="text-[12px] text-muted">{l}</div></div> }

function KwList({ items, color, title }) {
  const max = Math.max(...items.map((x) => Math.abs(x.weight)))
  return (
    <div>
      <div className="text-[13px] font-medium mb-2" style={{ color }}>{title}</div>
      <div className="space-y-1">
        {items.map((x) => (
          <div key={x.term} className="flex items-center gap-2 text-[12.5px]">
            <span className="w-28 truncate text-right text-ink">{x.term}</span>
            <span className="flex-1 h-3.5 rounded bg-slate-50"><span className="block h-3.5 rounded" style={{ width: `${(Math.abs(x.weight) / max) * 100}%`, background: color, opacity: 0.85 }} /></span>
            <span className="w-11 text-right tabular-nums text-muted">{nf(x.weight, 1)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Confusion({ m, labels }) {
  const n = m.length
  return (
    <div className="overflow-x-auto">
      <table className="mx-auto border-separate" style={{ borderSpacing: 3 }}>
        <thead><tr><th />{labels.map((l) => <th key={l} className="text-[12px] text-muted font-medium px-1 pb-1">{l}</th>)}</tr></thead>
        <tbody>
          {m.map((row, i) => {
            const s = row.reduce((a, b) => a + b, 0) || 1
            return (
              <tr key={i}>
                <th className="text-[12px] text-muted font-medium pr-2 text-right whitespace-nowrap">{labels[i]}</th>
                {row.map((v, j) => {
                  const r = v / s
                  return (
                    <td key={j} title={`Thật ${labels[i]} → dự đoán ${labels[j]}: ${nf(v)} (${pct(r)})`}
                      className={`text-center rounded-md ${n === 3 ? 'w-28 h-20' : 'w-16 h-14'}`}
                      style={{ background: `rgba(42,120,214,${0.06 + r * 0.9})`, color: r > 0.45 ? '#fff' : COLOR.ink, outline: i === j ? `2px solid ${COLOR.ink}22` : 'none' }}>
                      <div className="font-semibold tabular-nums text-[14px]">{pct(r, 0)}</div>
                      <div className="text-[11px] tabular-nums opacity-80">{nf(v)}</div>
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Mismatch({ n }) {
  const app = useApp()
  const [th, setTh] = useState(0.8)
  const [page, setPage] = useState(1)
  const r = useApi(() => api.mismatch({ threshold: th, page, page_size: 8 }), [th, page])
  return (
    <Card title="Đánh giá có số sao mâu thuẫn với nội dung" subtitle={`Trên tập kiểm tra: chấm 5 sao nhưng mô hình thấy tiêu cực, hoặc 1 sao nhưng nội dung tích cực (ngưỡng xác suất ≥ ${nf(th, 2)}) – ${nf(n)} đánh giá ở ngưỡng 0,8`}
      action={<label className="flex items-center gap-2 text-[12.5px] text-muted">Ngưỡng<input type="range" min="0.5" max="0.95" step="0.05" value={th} onChange={(e) => { setTh(Number(e.target.value)); setPage(1) }} /><span className="tabular-nums w-8">{nf(th, 2)}</span></label>}>
      {r.loading ? <Loading /> : r.error ? <ErrorBox error={r.error} /> : (
        <>
          <div className="grid md:grid-cols-2 gap-3">
            {r.data.items.map((x) => (
              <div key={x.review_id} className="rounded-lg border border-line p-3 text-[13px]">
                <div className="flex items-center gap-2 text-[12px] text-muted flex-wrap">
                  <span>Khách chấm</span><Stars value={x.score} size={12} /><span>· mô hình:</span>
                  <SentBadge s={x.pred_sentiment}>{SENT[x.pred_sentiment].label} {pct(x.pred_sentiment === 'neg' ? x.p_neg : x.p_pos, 0)}</SentBadge>
                  <button className="ml-auto font-mono text-[11.5px] hover:text-primary" onClick={() => app.openProduct(x.product_id)}>{x.product_id}</button>
                </div>
                <div className="font-medium text-ink mt-1.5">{x.summary}</div>
                <p className="text-text mt-0.5 line-clamp-3">{x.text}</p>
              </div>
            ))}
          </div>
          {r.data.items.length === 0 && <div className="text-[13px] text-muted">Không có đánh giá nào ở ngưỡng này.</div>}
          <Pager page={page} pageSize={8} total={r.data.page.total} onPage={setPage} />
        </>
      )}
    </Card>
  )
}

// Kết quả có đáng tin không: (1) kiểm tra theo thời gian – học trên dữ liệu cũ, kiểm tra trên năm cuối;
// (2) đối chiếu với thực nghiệm buổi 5 (notebook 02) khi dữ liệu là bộ đầy đủ
function Reliability({ tc, ref_, sel, sp }) {
  if (!tc && !ref_) return null
  const gap = tc ? (tc.random_f1_macro3 ?? sel.f1_macro3) - tc.f1_macro3 : null
  const rows = tc ? [
    [`Chia ngẫu nhiên 80/20 (${nf(sp.train)} học / ${nf(sp.test)} kiểm tra)`, tc.random_f1_macro3 ?? sel.f1_macro3, COLOR.primary],
    [`Theo thời gian: học trước ${tc.test_from?.slice(0, 7).split('-').reverse().join('/')}, kiểm tra ${tc.test_from?.slice(0, 7).split('-').reverse().join('/')} – ${tc.test_to?.slice(0, 7).split('-').reverse().join('/')}`, tc.f1_macro3, COLOR.ink],
  ] : []
  return (
    <Card title="Kết quả có đáng tin không?" subtitle="Hai kiểm tra bổ sung cho cách chia ngẫu nhiên – cùng mô hình Logistic Regression, cùng cấu hình">
      <div className="grid lg:grid-cols-2 gap-6">
        {tc && (
          <div>
            <div className="text-[13px] font-semibold text-ink">Kiểm tra theo thời gian</div>
            <p className="text-[12.5px] text-muted mt-0.5 leading-snug">Chia ngẫu nhiên có thể làm kết quả đẹp hơn thực tế (đánh giá gần giống nhau, cùng sản phẩm rơi vào cả tập học và tập kiểm tra).
              Ở đây mô hình chỉ học trên {nf(tc.n_train)} đánh giá cũ và dự đoán {nf(tc.n_test)} đánh giá mới hơn – đúng như khi dùng thật.</p>
            <div className="mt-3 space-y-2">
              {rows.map(([l, v, c]) => (
                <div key={l}>
                  <div className="flex justify-between text-[12.5px]"><span className="text-text">{l}</span><b className="tabular-nums text-ink">{nf(v, 3)}</b></div>
                  <div className="h-2 rounded-full bg-slate-100 mt-1 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: c }} /></div>
                </div>
              ))}
            </div>
            <p className="text-[12.5px] mt-3 leading-snug" style={{ color: Math.abs(gap) <= 0.02 ? COLOR.low : COLOR.medium }}>
              {Math.abs(gap) <= 0.02
                ? `Chênh lệch F1-macro ${nf(gap, 3)} (≤ 0,02): cách chia ngẫu nhiên không làm kết quả đẹp hơn đáng kể, mô hình học trên dữ liệu cũ vẫn dùng được cho giai đoạn mới.`
                : `Chênh lệch F1-macro ${nf(gap, 3)} (> 0,02): ngôn ngữ đánh giá thay đổi theo thời gian – nên huấn luyện lại định kỳ khi có dữ liệu mới.`}
              {' '}F1 lớp tiêu cực theo thời gian: {nf(tc.f1_neg, 3)}.
            </p>
          </div>
        )}
        {ref_ && (
          <div>
            <div className="text-[13px] font-semibold text-ink">Đối chiếu với thực nghiệm buổi 5 (notebook 02)</div>
            <table className="tbl mt-2">
              <thead><tr><th>Thiết lập</th><th className="text-right">Học / kiểm tra</th><th className="text-right">F1-macro</th></tr></thead>
              <tbody>
                <tr><td>Notebook – toàn bộ tập học 70%</td><td className="text-right tabular-nums">{nf(ref_.train)} / {nf(ref_.test)}</td><td className="text-right tabular-nums">{nf(ref_.f1_macro3, 3)}</td></tr>
                <tr><td>Notebook – theo thời gian (năm 2012)</td><td className="text-right tabular-nums">{nf(ref_.out_of_time_train)} / {nf(ref_.out_of_time_test)}</td><td className="text-right tabular-nums">{nf(ref_.out_of_time_f1, 3)}</td></tr>
                <tr className="bg-primarySoft/50"><td className="text-ink font-medium">Ứng dụng – mẫu phân tầng</td><td className="text-right tabular-nums">{nf(sp.train)} / {nf(sp.test)}</td><td className="text-right tabular-nums font-semibold text-ink">{nf(sel.f1_macro3, 3)}</td></tr>
              </tbody>
            </table>
            <p className="text-[12.5px] text-muted mt-2 leading-snug">Ứng dụng học trên mẫu {nf(sp.n_used)} đánh giá để cả quy trình xử lý xong trong vài phút (đường học ở notebook 02: thêm dữ liệu chỉ tăng F1 khoảng 0,01),
              nên F1 thấp hơn notebook {nf(ref_.f1_macro3 - sel.f1_macro3, 3)}. Con số trong báo cáo thiết kế ({nf(ref_.f1_macro3, 3)}) là của notebook; con số trên dashboard là của mô hình đang chạy.</p>
          </div>
        )}
      </div>
    </Card>
  )
}
