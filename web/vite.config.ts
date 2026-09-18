import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'

// Resolve API backend port dynamically:
// 1. VITE_API_PORT env var (set by nousetsu web --dev)
// 2. .api-port file written by nousetsu CLI
// 3. Default 5174
function resolveApiPort(): number {
  if (process.env.VITE_API_PORT) {
    return parseInt(process.env.VITE_API_PORT, 10)
  }
  try {
    const portFile = path.resolve(__dirname, '.api-port')
    const content = fs.readFileSync(portFile, 'utf-8').trim()
    const port = parseInt(content, 10)
    if (!isNaN(port)) return port
  } catch {
    // File doesn't exist — use default
  }
  return 5174
}

const apiPort = resolveApiPort()

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    open: false,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
})
