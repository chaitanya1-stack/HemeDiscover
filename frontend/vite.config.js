import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward these specific API requests to the FastAPI backend
      '/predict_heme_binding': 'http://127.0.0.1:8000',
      '/run_docking': 'http://127.0.0.1:8000',
      '/workspace': 'http://127.0.0.1:8000'
    }
  }
})