// Light / dark appearance. 'system' (the default) follows the operating system; 'light' and 'dark' are the user's
// own choice, kept per browser and put on <html data-theme> (tokens.css has the colours for both).
// Base.astro applies a stored choice before the first paint; this module changes it afterwards.
export type Theme = 'system' | 'light' | 'dark';
export const THEMES: Theme[] = ['system', 'light', 'dark'];
export const THEME_STORE = 'ipush.theme';
const EVENT = 'ipush:theme';

export function getTheme(): Theme {
  try { const t = localStorage.getItem(THEME_STORE); if (t === 'light' || t === 'dark') return t; } catch { /* private mode */ }
  return 'system';
}

export function setTheme(t: Theme) {
  try { if (t === 'system') localStorage.removeItem(THEME_STORE); else localStorage.setItem(THEME_STORE, t); } catch { /* private mode */ }
  if (t === 'system') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  window.dispatchEvent(new Event(EVENT));
}

/** Calls back when the colours on screen change: the user picked a theme, or the system switched while following it. */
export function onThemeChange(cb: () => void): () => void {
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  window.addEventListener(EVENT, cb);
  mq.addEventListener('change', cb);
  return () => { window.removeEventListener(EVENT, cb); mq.removeEventListener('change', cb); };
}
