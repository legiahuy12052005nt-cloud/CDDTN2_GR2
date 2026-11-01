// Biểu tượng: khung bình luận + ngôi sao (đánh giá của khách hàng)
export function BrandMark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="3" width="28" height="22" rx="7" fill="#2a78d6" />
      <path d="M9 25 L9 30 L15 25 Z" fill="#2a78d6" />
      <path d="M16 7.5l2.2 4.6 5 .6-3.7 3.4 1 4.9L16 18.6 11.5 21l1-4.9-3.7-3.4 5-.6z" fill="#fff" />
    </svg>
  )
}
