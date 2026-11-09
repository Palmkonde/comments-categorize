import { marked } from 'marked';

// Markdown notes in this folder render in place. HTML pages in pages/ load in an iframe,
// so their own styles, MathJax and Mermaid keep working untouched.
const notes = import.meta.glob('./*.md', { query: '?raw', import: 'default', eager: true });

const routes = {};
for (const [path, text] of Object.entries(notes)) {
  const slug = path.slice(2, -3);
  routes[slug] = { title: text.match(/^# (.+)$/m)?.[1] ?? slug, kind: 'Note', text };
}
for (const p of __PAGES__) routes[p.slug] = { title: p.title, kind: 'Page' };

const nav = document.querySelector('nav');
const view = document.querySelector('#view');

nav.innerHTML = Object.entries(routes)
  .sort(([, a], [, b]) => a.title.localeCompare(b.title))
  .map(([slug, r]) => `<a href="#/${slug}" data-slug="${slug}"><small>${r.kind}</small>${r.title}</a>`)
  .join('');

function render() {
  const slug = location.hash.slice(2);
  const r = routes[slug];
  for (const a of nav.querySelectorAll('a')) a.classList.toggle('on', a.dataset.slug === slug);
  if (!r) {
    view.innerHTML = '<article><h1>JEV research</h1><p>Pick a note or page on the left.</p></article>';
  } else if (r.text) {
    view.innerHTML = `<article>${marked.parse(r.text)}</article>`;
    for (const a of view.querySelectorAll('a[href^="http"]')) a.target = '_blank';
  } else {
    view.innerHTML = `<iframe src="pages/${slug}.html" title="${r.title}"></iframe>`;
  }
  document.title = r ? `${r.title} · JEV research` : 'JEV research';
  view.scrollTop = 0;
}

addEventListener('hashchange', render);
render();
