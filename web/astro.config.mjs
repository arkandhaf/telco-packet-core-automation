import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import { clientBundlePlugin } from './scripts/build-client.mjs';

export default defineConfig({
  output: 'static',
  outDir: './dist',
  vite: {
    plugins: [tailwindcss(), clientBundlePlugin()],
    // Avoid Windows drive-canonicalization probes outside restricted workspaces.
    resolve: { preserveSymlinks: true },
    server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  },
});
