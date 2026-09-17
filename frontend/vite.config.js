import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/verp',
    }),
    vue(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  optimizeDeps: {
    // frappe-ui's TextEditor imports icons via unplugin-icons' `~icons/lucide/*`
    // virtual modules, resolved by the lucideIcons() Vite plugin (registered
    // above via frappeui()). That plugin's resolveId/load hooks only run in
    // Vite's normal dev-transform pipeline, not in the esbuild-based
    // optimizeDeps scanner used to prebundle bare imports from node_modules -
    // so scanning frappe-ui with esbuild crashes on those unresolved paths.
    // Excluding it here skips that scan and serves it through the regular
    // pipeline instead, where the virtual modules resolve fine.
    exclude: ['frappe-ui'],
  },
})
