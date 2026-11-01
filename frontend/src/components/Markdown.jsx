import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Hiển thị câu trả lời Markdown (bảng, danh sách, in đậm) của trợ lý; không cho phép HTML thô.
export default function Markdown({ children }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        a: ({ node, ...p }) => <a {...p} target="_blank" rel="noreferrer" />,       // eslint-disable-line no-unused-vars
        table: ({ node, ...p }) => <div className="md-table"><table {...p} /></div>, // eslint-disable-line no-unused-vars
      }}>
        {children || ''}
      </ReactMarkdown>
    </div>
  )
}
