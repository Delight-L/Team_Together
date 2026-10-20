import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes('administrative-regions.json')) return 'map-boundaries';
    if (id.includes('node_modules')) return 'vendor';
  } } } },
  server: { port: 5173, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8503', '/brand': 'http://127.0.0.1:8503' } },
});
