import { defineConfig } from 'vite';

// Vite configuration with CORS proxy for backend integration (Section 2.9)
export default defineConfig({
  server: {
    port: 3000,
    open: true,
    cors: true,
    proxy: {
      // Proxy student query and incident endpoints to Saket's backend
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/incidents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
});

