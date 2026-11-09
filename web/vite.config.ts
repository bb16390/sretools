import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

/**
 * 后端 master 服务默认地址。
 * 开发期通过代理复用现有 FastAPI 路由，避免跨域与 Cookie 问题。
 */
const backend = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5500'

export default defineConfig({
  plugins: [vue()],
  // 生产托管在 /web 下时，用 VITE_BASE=/web/ 构建；直接托管根路径则保持 '/'
  base: process.env.VITE_BASE || '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/admin': { target: backend, changeOrigin: false },
      '/api': { target: backend, changeOrigin: false },
      '/static': { target: backend, changeOrigin: false },
    },
  },
})
