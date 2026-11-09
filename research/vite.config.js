import { defineConfig } from 'vite';
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Every pages/*.html is its own Vite entry and gets a route at #/<file name>.
const dir = resolve(import.meta.dirname, 'pages');
const pages = readdirSync(dir).filter((f) => f.endsWith('.html')).map((f) => ({
  slug: f.slice(0, -5),
  title: readFileSync(resolve(dir, f), 'utf8').match(/<title>(.*?)<\/title>/)?.[1] ?? f,
}));

export default defineConfig({
  base: './',
  define: { __PAGES__: JSON.stringify(pages) },
  build: {
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, 'index.html'),
        ...Object.fromEntries(pages.map((p) => [p.slug, resolve(dir, `${p.slug}.html`)])),
      },
    },
  },
});
