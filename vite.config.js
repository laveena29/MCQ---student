import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: [
      'c4cd3943-3c59-4567-96f5-876582ac947d-00-2csb2w697qy9k.sisko.replit.dev'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:5000', // Backend Flask Repl or local server
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
