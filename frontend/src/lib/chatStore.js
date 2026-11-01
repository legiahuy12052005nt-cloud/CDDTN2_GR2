import { useSyncExternalStore } from 'react'

// Lịch sử hội thoại dùng chung cho khung chat nổi và khung chat trong tab Trợ lý AI (lưu tạm trong sessionStorage).
const KEY = 'fri_chat_v1'
let state = (() => { try { return JSON.parse(window.sessionStorage.getItem(KEY)) || { messages: [], pending: false } } catch { return { messages: [], pending: false } } })()
state.pending = false
const subs = new Set()
const emit = () => { try { window.sessionStorage.setItem(KEY, JSON.stringify({ ...state, pending: false })) } catch { /* bỏ qua */ } subs.forEach((f) => f()) }

export const chatStore = {
  get: () => state,
  subscribe: (f) => { subs.add(f); return () => subs.delete(f) },
  push: (m) => { state = { ...state, messages: [...state.messages, m] }; emit() },
  setPending: (p) => { state = { ...state, pending: p }; emit() },
  clear: () => { state = { messages: [], pending: false }; emit() },
}
export const useChat = () => useSyncExternalStore(chatStore.subscribe, chatStore.get)
