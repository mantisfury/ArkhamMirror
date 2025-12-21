import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ArkhamMirror/ach/', // GitHub Pages subfolder path
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
