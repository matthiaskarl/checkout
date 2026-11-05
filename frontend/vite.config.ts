import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // Served by Apache at https://HOST/app/ in production.
  base: '/app/',
  plugins: [react()],
  server: {
    proxy: {
      // Dev only: forward /api/* to the uvicorn dev server, so the app can always
      // call relative /api/... URLs (same origin, no CORS needed).
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
