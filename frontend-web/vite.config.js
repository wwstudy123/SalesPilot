import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8080',
                changeOrigin: true,
            },
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
