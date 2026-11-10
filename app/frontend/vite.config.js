import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/consumption': 'http://localhost:8080',
      '/anomalies': 'http://localhost:8080',
      '/forecast': 'http://localhost:8080',
      '/chat': 'http://localhost:8080',
    }
  }
})
