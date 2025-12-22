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
    // Disable modulepreload for large chunks to improve initial load
    modulePreload: {
      resolveDependencies: (filename, deps) => {
        // Don't preload charts - they're lazy loaded
        return deps.filter(dep => !dep.includes('charts'))
      }
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Core React - always needed
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) {
            return 'vendor-react'
          }
          // Router - always needed
          if (id.includes('@tanstack/react-router')) {
            return 'vendor-router'
          }
          // Query - always needed
          if (id.includes('@tanstack/react-query')) {
            return 'vendor-query'
          }
          // Table - needed on market/admin pages
          if (id.includes('@tanstack/react-table')) {
            return 'vendor-table'
          }
          // Icons - frequently used
          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }
          // NOTE: Charts (recharts) removed from manual chunks - Vite handles it better
          // with mixed lazy/direct imports across components
        }
      }
    }
  },
  cacheDir: 'node_modules/.vite'
})

