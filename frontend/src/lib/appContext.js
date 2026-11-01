import { createContext, useContext } from 'react'

// Ngữ cảnh ứng dụng: trạng thái hệ thống, mở chi tiết sản phẩm, chuyển tab, mở trợ lý AI với ngữ cảnh màn hình.
export const AppCtx = createContext(null)
export const useApp = () => useContext(AppCtx)
