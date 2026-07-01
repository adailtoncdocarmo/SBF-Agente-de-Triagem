import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O FastAPI serve o build (`dist`) na raiz "/"; no dev, o Vite roda em :5173
// e faz proxy de /api para o backend em :8000.
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
