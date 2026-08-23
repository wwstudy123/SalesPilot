import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            input: {
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
                configure: function (proxy) {
                    proxy.on('proxyReq', function (proxyReq, req) {
                        var _a;
                        // Internal API 使用 Bearer Token 鉴权；SSE 端点关闭缓冲
                        proxyReq.setHeader('Authorization', 'Bearer secret-token');
                        if ((_a = req.url) === null || _a === void 0 ? void 0 : _a.includes('/stream')) {
                            proxyReq.setHeader('Accept', 'text/event-stream');
                            proxyReq.setHeader('Cache-Control', 'no-cache');
                        }
                    });
                },
            },
        },
    },
});
