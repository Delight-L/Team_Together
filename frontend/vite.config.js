import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks(id) {
    if (id.includes('administrative-regions.json')) return 'map-boundaries';
    if (id.includes('node_modules') && id.includes('leaflet')) return 'leaflet';
    if (id.includes('node_modules')) return 'vendor';
  } } } },
  server: { proxy: { '/api': 'http://127.0.0.1:8503', '/brand': 'http://127.0.0.1:8503' } },
});
