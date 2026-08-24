import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        index: 'index.html',
        admin: 'admin.html',
        sidebar: 'sidebar.html',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // sale-agent（AI 交互，SSE）——必须放在 '/api' 之前以优先匹配
      '/api/ai': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // business-mock（业务 CRUD）
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // 遗留 Internal API（sale-agent 现有 run 管理端点，M2 起迁移到 /api/ai）
      '/internal': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Internal API 使用 Bearer Token 鉴权；SSE 端点关闭缓冲
            proxyReq.setHeader('Authorization', 'Bearer secret-token')
            if (req.url?.includes('/stream')) {
              proxyReq.setHeader('Accept', 'text/event-stream')
              proxyReq.setHeader('Cache-Control', 'no-cache')
            }
          })
        },
      },
    },
  },
})
