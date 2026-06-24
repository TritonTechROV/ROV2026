import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5002,
    strictPort: true,
    hmr: {
      host: '10.42.0.1',
    },
    proxy: {
      '/dimensions': {
        target: 'https://localhost:5000',
        secure: false,
      },
    },
  },
});
