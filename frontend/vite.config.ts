import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'attendance-report-route',
      configureServer(server) {
        server.middlewares.use((request, _response, next) => {
          if (request.url) {
            request.url = request.url.replace(/^\/attendance\/?(?=\?|$)/, '/attendance/index.html');
          }
          next();
        });
      },
    },
  ],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
});
