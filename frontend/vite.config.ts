import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './app'),
      '~': path.resolve(__dirname, './app')
    },
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.json']
  },
  server: {
    port: 3000,
    fs: {
      strict: false
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunk - core React libraries
          'vendor-react': ['react', 'react-dom'],
          // Router chunk
          'vendor-router': ['@tanstack/react-router'],
          // Query chunk
          'vendor-query': ['@tanstack/react-query'],
          // Table chunk - only needed on dashboard/market pages
          'vendor-table': ['@tanstack/react-table'],
          // Charts chunk - heavy (~200KB), only needed on market/card detail
          'vendor-charts': ['recharts'],
          // Icons chunk
          'vendor-icons': ['lucide-react'],
        }
      }
    }
  },
  cacheDir: 'node_modules/.vite'
})

