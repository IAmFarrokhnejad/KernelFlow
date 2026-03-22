import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: './postcss.config.js'
  },
  resolve: {
    alias: {
      "@": "/src"
    }
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})