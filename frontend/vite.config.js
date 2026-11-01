import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Khi chạy dev, mọi lời gọi /api được chuyển tới backend FastAPI (cổng 8000).
// Trong Docker, BACKEND_URL = http://backend:8000
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: process.env.BACKEND_URL || 'http://localhost:8000', timeout: 600000, proxyTimeout: 600000 } } },
  build: {
    rollupOptions: { output: { manualChunks: { charts: ['recharts'], markdown: ['react-markdown', 'remark-gfm'] } } },
    chunkSizeWarningLimit: 700,
  },
})
