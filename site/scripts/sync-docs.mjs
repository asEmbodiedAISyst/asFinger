// Turns the hand-written docs in ../docs into what the site serves (run before dev/build). Everything written
// here is generated and git-ignored; edit the files in docs/, never the copies.
//
//   docs/en/<path>.md -> src/content/docs/docs/<path>.md      Starlight page  /docs/<path>/      (English, root locale)
//   docs/zh/<path>.md -> src/content/docs/zh/docs/<path>.md   Starlight page  /zh/docs/<path>/   (Chinese)
//   the same files, unchanged -> public/docs/<path>.md and public/zh/docs/<path>.md   (the Markdown originals)
//   docs/assets/<file>    -> public/docs-assets/<file>       pictures that a page shows (linked as ../../assets/<file>)
//   public/llms.txt       index of every page, linking to the Markdown originals (https://llmstxt.org)
//   public/llms-full.txt  every page in one file
//
// A page's title is its first `# heading`; its description is the first paragraph after it. Links between pages
// are written as relative links to the .md files (so they also work on GitHub) and are rewritten to site paths.
// The order of the pages in the sidebar and in llms.txt is ORDER below; a page that is not listed goes last.
import { copyFileSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync, statSync, existsSync } from 'node:fs';
import { dirname, join, posix, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const site = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(process.env.ASFINGER_ROOT || join(site, '..'));
const docs = join(repo, 'docs');
const content = join(site, 'src', 'content', 'docs');
const pub = join(site, 'public');

const SITE_URL = (process.env.SITE_URL || 'https://asembodiedaisyst.github.io').replace(/\/$/, '');
const BASE = ('/' + (process.env.BASE_PATH || '/').replace(/^\/|\/$/g, '') + '/').replace('//', '/');   // '/' or '/asFinger/'
const REPO_URL = 'https://github.com/asEmbodiedAISyst/asFinger';

const LOCALES = [
  { dir: 'en', prefix: '', name: 'English' },
  { dir: 'zh', prefix: 'zh/', name: '中文' },
];
const SECTIONS = [
  { dir: 'user', en: 'User guide', zh: '使用指南' },
  { dir: 'developer', en: 'Developer guide', zh: '开发指南' },
  { dir: 'agents', en: 'Agent guides', zh: 'Agent 指南' },
];
const ORDER = {
  '': ['index', 'glossary'],
  user: ['index', 'installation', 'quickstart', 'config-file', 'frames', 'checks', 'mjcf', 'editor', 'fusion', 'robot-setup', 'robot-arm-tools', 'robot-calibration', 'teleoperation', 'data-collection', 'simulation', 'simulation-twin', 'troubleshooting'],
  developer: ['index', 'architecture', 'decisions', 'contributing', 'roadmap'],
  agents: ['index', 'using', 'developing'],
};

function walk(dir, rel = '') {
  const out = [];
  for (const f of readdirSync(dir).sort()) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) out.push(...walk(p, rel ? `${rel}/${f}` : f));
    else if (f.endsWith('.md')) out.push(rel ? `${rel}/${f}` : f);
  }
  return out;
}

const rank = (rel) => {
  const section = rel.includes('/') ? rel.split('/')[0] : '';
  const name = rel.split('/').pop().replace(/\.md$/, '');
  const i = (ORDER[section] || []).indexOf(name);
  return i < 0 ? 999 : i;
};

/** "user/quickstart.md" -> "docs/user/quickstart/", "user/index.md" -> "docs/user/", "index.md" -> "docs/" */
const routeOf = (rel) => `docs/${rel.replace(/\.md$/, '')}/`.replace(/(^|\/)index\/$/, '$1');

function parse(src) {
  const m = src.match(/^#\s+(.+?)\s*$/m);
  if (!m) throw new Error('page without a "# title"');
  const body = src.slice(m.index + m[0].length).replace(/^\s*\n/, '');
  const para = body.split(/\n\s*\n/)[0] || '';
  const plain = para.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[`*_]/g, '').replace(/\s+/g, ' ').trim();
  // only a plain paragraph makes a description (not a list, a table, a quote, a heading or a code block)
  const description = /^[#>|\-*`\d]/.test(para.trim()) ? '' : plain;
  return { title: m[1], body, description };
}

/** Rewrite relative links to other docs pages into site paths; links that leave docs/ point at the repository. */
function relink(body, rel, loc) {
  return body.replace(/(\]\()([^)\s]+)(\))/g, (all, a, href, c) => {
    if (/^([a-z]+:|#|\/)/i.test(href)) return all;
    const [path, hash = ''] = href.split('#');
    const target = posix.normalize(posix.join(posix.dirname(`${loc.dir}/${rel}`), path));
    if (target.startsWith('../')) return `${a}${REPO_URL}/blob/main/${target.replace(/^(\.\.\/)+/, '')}${hash ? '#' + hash : ''}${c}`;
    if (/^assets\/.+\.(png|jpe?g|svg|webp|gif)$/i.test(target)) {   // a picture in docs/assets: served from public/docs-assets
      const out = join(pub, 'docs-assets', target.slice('assets/'.length));
      mkdirSync(dirname(out), { recursive: true });
      copyFileSync(join(docs, target), out);
      return `${a}${BASE}docs-assets/${target.slice('assets/'.length)}${c}`;
    }
    const [lang, ...rest] = target.split('/');
    const l = LOCALES.find((x) => x.dir === lang);
    if (!l || !target.endsWith('.md')) return `${a}${REPO_URL}/blob/main/docs/${target}${hash ? '#' + hash : ''}${c}`;
    return `${a}${BASE}${l.prefix}${routeOf(rest.join('/'))}${hash ? '#' + hash : ''}${c}`;
  });
}

const yaml = (s) => JSON.stringify(s);

rmSync(content, { recursive: true, force: true });
for (const l of LOCALES) rmSync(join(pub, l.prefix, 'docs'), { recursive: true, force: true });
rmSync(join(pub, 'docs-assets'), { recursive: true, force: true });

const pages = [];   // { loc, rel, title, description, route, md, raw }
for (const loc of LOCALES) {
  const root = join(docs, loc.dir);
  if (!existsSync(root)) throw new Error(`missing ${root}`);
  for (const rel of walk(root)) {
    const raw = readFileSync(join(root, rel), 'utf8');
    let page;
    try { page = parse(raw); } catch (e) { throw new Error(`docs/${loc.dir}/${rel}: ${e.message}`); }
    const fm = ['---', `title: ${yaml(page.title)}`];
    if (page.description) fm.push(`description: ${yaml(page.description)}`);
    fm.push('sidebar:', `  order: ${rank(rel)}`, '---', '');
    const out = join(content, loc.prefix, 'docs', rel);
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, fm.join('\n') + '\n' + relink(page.body, rel, loc));
    const md = join(pub, loc.prefix, 'docs', rel);
    mkdirSync(dirname(md), { recursive: true });
    writeFileSync(md, raw);
    pages.push({ loc, rel, ...page, route: `${loc.prefix}${routeOf(rel)}`, md: `${loc.prefix}docs/${rel}`, raw });
  }
}

// The page for an address that does not exist. Static hosts serve this one file for every language.
writeFileSync(join(content, '404.md'), `---
title: "Page not found"
template: splash
editUrl: false
pagefind: false
hero:
  title: "404"
  tagline: "This page does not exist. 页面不存在。"
  actions:
    - text: "Documentation"
      link: "${BASE}docs/"
    - text: "中文文档"
      link: "${BASE}zh/docs/"
      variant: minimal
---
`);

// Both languages must have the same pages.
const sets = LOCALES.map((l) => pages.filter((p) => p.loc === l).map((p) => p.rel).sort().join('\n'));
if (new Set(sets).size !== 1) throw new Error('docs/en and docs/zh do not have the same pages');

const abs = (path) => `${SITE_URL}${BASE}${path}`;
const sorted = (loc, section) => pages
  .filter((p) => p.loc === loc && (section ? p.rel.startsWith(section + '/') : !p.rel.includes('/')))
  .sort((a, b) => rank(a.rel) - rank(b.rel) || a.rel.localeCompare(b.rel));
const line = (p) => `- [${p.title}](${abs(p.md)})${p.description ? ': ' + p.description : ''}`;

const en = LOCALES[0];
const home = pages.find((p) => p.loc === en && p.rel === 'index.md');
const llms = [`# asFinger`, '', `> ${home?.description || 'A parametric push rod with a phone as the wrist camera.'}`, '',
  `Documentation site: ${abs('docs/')}. Web editor: ${abs('editor/')}. Source: ${REPO_URL}.`,
  `Every link below is the Markdown source of one page. All pages in one file: ${abs('llms-full.txt')}`, ''];
for (const loc of LOCALES) {
  const t = (s) => (loc === en ? s.en : `${s.zh}（${loc.name}）`);
  llms.push(`## ${loc === en ? 'Overview' : `概览（${loc.name}）`}`, '', ...sorted(loc, '').map(line), '');
  for (const s of SECTIONS) llms.push(`## ${t(s)}`, '', ...sorted(loc, s.dir).map(line), '');
}
writeFileSync(join(pub, 'llms.txt'), llms.join('\n'));

const full = [llms.slice(0, 5).join('\n')];
for (const loc of LOCALES) {
  for (const section of ['', ...SECTIONS.map((s) => s.dir)]) {
    for (const p of sorted(loc, section)) full.push(`<!-- ${abs(p.md)} -->\n\n${p.raw.trim()}`);
  }
}
writeFileSync(join(pub, 'llms-full.txt'), full.join('\n\n---\n\n') + '\n');

console.log(`[sync-docs] ${pages.length} pages (${LOCALES.map((l) => l.dir).join(', ')}), llms.txt, llms-full.txt -> src/content/docs, public/`);
