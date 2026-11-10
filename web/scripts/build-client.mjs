import { build, context } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const options = {
  absWorkingDir: root,
  entryPoints: ['src/scripts/bootstrap.ts'],
  outfile: resolve(root, 'public/assets/relpool-app.js'),
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: ['es2020'],
  minify: true,
  sourcemap: 'external',
  legalComments: 'eof',
  define: { 'process.env.NODE_ENV': '"production"' },
};

export function clientBundlePlugin() {
  return {
    name: 'relpool-client-bundle',
    // Astro also creates a temporary Vite server for type generation/builds.
    // Start the watcher only for the interactive dev command.
    apply: (_config, environment) => environment.command === 'serve' && process.argv.includes('dev'),
    async configureServer(server) {
      const watcher = await context(options);
      await watcher.watch();
      server.httpServer?.once('close', () => { void watcher.dispose(); });
    },
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await build(options);
  console.log('RELPOOL client: GSAP + application bundled for ES2020 browsers.');
}
