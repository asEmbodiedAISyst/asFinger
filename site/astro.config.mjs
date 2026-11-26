// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import starlight from '@astrojs/starlight';

// Where the site is served. The defaults serve it at the root, which suits `npm run dev`. A GitHub Pages project
// site (https://<owner>.github.io/<repo>/) sets both: SITE_URL=https://<owner>.github.io BASE_PATH=/<repo>/
// (.github/workflows/pages.yml takes them from the repository's Pages settings).
const env = /** @type {any} */ (globalThis).process?.env ?? {};
const site = env.SITE_URL || 'https://asembodiedaisyst.github.io';
const base = env.BASE_PATH || '/';

// The landing page and the editor are plain Astro pages (src/pages). Starlight serves the documentation under
// /docs/ (English, the root locale) and /zh/docs/ (Chinese). Its content is generated from ../docs by
// scripts/sync-docs.mjs; the sections below are the three folders docs/<language>/{user,developer,agents}.
const section = (/** @type {string} */ label, /** @type {string} */ zh, /** @type {string} */ dir) =>
  ({ label, translations: { 'zh-CN': zh }, items: [{ autogenerate: { directory: `docs/${dir}` } }] });

export default defineConfig({
  site,
  base,
  output: 'static',
  integrations: [
    starlight({
      title: 'asFinger',
      description: 'asFinger: a parametric push rod with a phone as the wrist camera, for a robot arm or a human hand.',
      favicon: '/favicon.svg',
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        zh: { label: '中文', lang: 'zh-CN' },
      },
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/asEmbodiedAISyst/asFinger' }],
      sidebar: [
        { label: 'Overview', translations: { 'zh-CN': '概览' }, slug: 'docs' },
        section('User guide', '使用指南', 'user'),
        section('Developer guide', '开发指南', 'developer'),
        section('Agent guides', 'Agent 指南', 'agents'),
        { label: 'Glossary', translations: { 'zh-CN': '术语表' }, slug: 'docs/glossary' },
      ],
      customCss: ['./src/styles/docs.css'],
    }),
    react(),
  ],
  vite: {
    worker: { format: 'es' },
    optimizeDeps: { exclude: ['manifold-3d'] },
  },
});
