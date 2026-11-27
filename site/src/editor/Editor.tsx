// The editor page: state lives here, the pieces only render it.
// The 3D view fills the window; everything else floats over it. Names used in discussion (code names in brackets):
//   View    (CenterPanel, .stage)   the 3D view; SelectionBar (.summary) in the top strip says what is selected
//   Config  (LeftPanel)             rail on the left (.rail, always there) + the cards of one group (.left, closed at first)
//   Inspect (.right)                Info (InfoPanel, top) | splitter | Params (ParamsPanel, bottom); closed at first
//   selection  which item is picked in each group          (persisted per browser)
//   active     the group in focus, or 'overall': the view looks at it, Inspect is about it
//   solo       the active group is shown alone instead of inside the full assembly
//   edits      pusher parameters the user changed           (persisted per browser)
// Config always works on the full assembly: picking a group or a card moves the camera to that part.
// A chip of the selection bar shows that part alone; the same chip or "Full assembly" goes back.
// Who decides a pusher parameter, strongest first:
//   fixed      the flange adapter (its height, screw direction, hole pattern on its tool side), the phone (its size and
//              camera positions) and, when the pusher is bolted on directly (adapter "None"), the carrier's flange
//              pattern; read-only in the panel
//   edits      what the user typed
//   defaults   per carrier: the mounting angle mount_rot (and what a direct mount needs), so every arm looks alike
//   config     the values in the pusher config file
// Every change of these re-solves the model in the worker; the newest request wins.
import type React from 'react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { GROUPS, DEFAULT_SELECTION, item, fits } from '../data/catalog';
import { isLocked } from '../data/pusherParams';
import { FLANGES } from '../data/flanges';
import { Engine } from '../engine/client';
import type { ParamValue, SolveResult } from '../engine/types';
import { LeftPanel } from './LeftPanel';
import { CenterPanel, SelectionBar, type Insets } from './CenterPanel';
import { InfoPanel } from './InfoPanel';
import { ParamsPanel, type Exporter, type Preset } from './ParamsPanel';
import { Ico, Logo } from './icons';
import type { SceneContent } from './scene';
import { LangContext, LANGS, LANG_LABEL, PRODUCT, langPath, makeT, tx, type Lang } from '../i18n';
import { THEMES, getTheme, setTheme, type Theme } from '../theme';
import './editor.css';

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
const STORE = 'ipush.editor.v3', STORE_OLD = ['ipush.editor.v2', 'ipush.editor.v1'];

interface Saved { selection?: Record<string, string>; edits?: Record<string, ParamValue>; active?: string; solo?: boolean; inspect?: boolean; split?: number }

// Inspect column: share of the height taken by the info part (top); the splitter keeps it within 1/3 .. 2/3.
const SPLIT_MIN = 1 / 3, SPLIT_MAX = 2 / 3, SPLIT_DEFAULT = 0.42;
const clampSplit = (f: number) => Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, f));
const load = (): Saved => {
  try {
    const s = localStorage.getItem(STORE);
    if (s) return JSON.parse(s);
    // Older versions: start from the defaults again. Their parameter edits were kept across layouts and, with
    // Inspect closed, changed the model without anything on screen saying so. The old entries are left in place.
    for (const k of STORE_OLD) { const o = localStorage.getItem(k); if (o) return { split: JSON.parse(o).split }; }
    return {};
  } catch { return {}; }
};
const save = (s: Saved) => { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch { /* private mode */ } };

function download(name: string, data: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Editor({ lang = 'en' }: { lang?: Lang }) {
  const t = useMemo(() => makeT(lang), [lang]);
  const saved = useMemo(load, []);
  const [selection, setSelection] = useState<Record<string, string>>(() => {
    const s = { ...DEFAULT_SELECTION, ...saved.selection };
    for (const g of GROUPS) { const it = item(g.id, s[g.id]); if (!it || it.disabled) s[g.id] = DEFAULT_SELECTION[g.id]; }
    if (!fits(item('adapter', s.adapter), s.carrier)) s.adapter = item('carrier', s.carrier)?.defaultAdapter ?? 'none';
    return s;
  });
  const [active, setActive] = useState<string>(saved.active && GROUPS.some((g) => g.id === saved.active) ? saved.active : 'overall');
  const [solo, setSolo] = useState(!!saved.solo);
  const [edits, setEdits] = useState<Record<string, ParamValue>>(saved.edits ?? {});
  const [configOpen, setConfigOpen] = useState(false);          // both panels start closed: the view comes first
  const [inspectOpen, setInspectOpen] = useState(!!saved.inspect);
  const [split, setSplit] = useState(() => clampSplit(saved.split ?? SPLIT_DEFAULT));
  const rootRef = useRef<HTMLDivElement>(null);
  const inspectRef = useRef<HTMLElement>(null);
  const [insets, setInsets] = useState<Insets>({ l: 0, r: 0, t: 0, b: 0 });
  const [config, setConfig] = useState<any | null>(null);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [engineState, setEngineState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  // light / dark: 'system' until the user picks one (read after mount: the server-rendered page cannot know it)
  const [theme, setThemeState] = useState<Theme>('system');
  useEffect(() => setThemeState(getTheme()), []);
  const pickTheme = useCallback((th: Theme) => { setTheme(th); setThemeState(th); }, []);
  const engine = useRef<Engine | null>(null);

  useEffect(() => save({ selection, edits, active, solo, inspect: inspectOpen, split }), [selection, edits, active, solo, inspectOpen, split]);

  // What the floating pieces cover: the view keeps the model in the middle of the rest.
  useLayoutEffect(() => {
    const measure = () => {
      const el = rootRef.current;
      if (!el) return;
      const box = el.getBoundingClientRect();
      const rect = (q: string) => el.querySelector(q)?.getBoundingClientRect();
      const L = rect('.left'), R = rect('.right'), T = rect('.topbar'), B = rect('.vp-bottom');
      const n = { l: L ? L.right - box.left : 0, r: R ? box.right - R.left : 0, t: T ? T.bottom - box.top : 0, b: B ? box.bottom - B.top : 0 };
      setInsets((o) => (o.l === n.l && o.r === n.r && o.t === n.t && o.b === n.b ? o : n));
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [configOpen, inspectOpen, active]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setConfigOpen(false); };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);

  const carrier = item('carrier', selection.carrier);
  const adapter = item('adapter', selection.adapter);
  const pusher = item('pusher', selection.pusher);
  const camera = item('camera', selection.camera);
  const direct = adapter?.option === false;          // no adapter: the pusher base sits on the robot flange
  const custom = !!carrier?.customFlange;

  // engine
  useEffect(() => {
    const e = new Engine();
    engine.current = e;
    e.init().then(() => setEngineState('ready'), (err) => { setEngineState('error'); setError(String(err?.message || err)); });
  }, []);

  // pusher base config
  useEffect(() => {
    if (!pusher?.config) return;
    let live = true;
    fetch(`${BASE}/${pusher.config}`).then((r) => r.json()).then((c) => {
      if (!live) return;
      setConfig(c);
      // drop stored edits for parameters this config does not have (the config may have changed since)
      setEdits((e) => Object.fromEntries(Object.entries(e).filter(([k]) => k in c.params)));
    }).catch((err) => setError(t('configLoadFailed') + err));
    return () => { live = false; };
  }, [pusher?.config]);

  const fixed = useMemo(() => {
    const out: Record<string, { value: number; by: string }> = {};
    const put = (g: number, it: typeof carrier) => {
      for (const [k, v] of Object.entries(it?.sets ?? {})) out[k] = { value: v, by: `${tx(GROUPS[g].title, lang)} (${tx(it!.name, lang)})` };
    };
    if (direct && !custom) put(0, carrier);
    put(1, adapter);
    put(GROUPS.findIndex((g) => g.id === 'camera'), camera);
    return out;
  }, [carrier, adapter, camera, direct, custom, lang]);

  const defaults = useMemo(() => {
    const d: Record<string, number> = {};
    if (carrier?.mountRot !== undefined) d.mount_rot = carrier.mountRot;
    if (direct) Object.assign(d, carrier?.direct?.defaults);
    return d;
  }, [carrier, direct]);

  const params = useMemo(() => {
    const p: Record<string, ParamValue> = { ...defaults };
    for (const [k, v] of Object.entries(edits)) if (!isLocked(k, fixed, custom)) p[k] = v;
    for (const [k, v] of Object.entries(fixed)) p[k] = v.value;
    return p;
  }, [edits, fixed, defaults, custom]);

  const options = useMemo(() => ({ ...camera?.options, g1_adapter: false, ...adapter?.options, adapter: !direct }), [camera, adapter, direct]);

  useEffect(() => {
    if (engineState !== 'ready' || !config || !engine.current) return;
    let live = true;
    setBusy(true);
    engine.current.solve(config, params, options, lang).then((r) => {
      if (!live || !r) return;
      setResult(r); setError(null); setBusy(false);
    }, (err) => { if (live) { setError(String(err?.message || err).split('\n').filter(Boolean).pop() ?? '?'); setBusy(false); } });
    return () => { live = false; };
  }, [engineState, config, params, options, lang]);

  const onChange = useCallback((k: string, v: number | undefined) => {
    setEdits((e) => { const n = { ...e }; if (v === undefined) delete n[k]; else n[k] = v; return n; });
  }, []);

  // Picking a carrier also picks its usual adapter; a new carrier or adapter starts from its own defaults again.
  const onSelect = useCallback((g: string, id: string) => {
    setSelection((s) => {
      const n = { ...s, [g]: id };
      if (g === 'carrier' && id !== s.carrier) n.adapter = item('carrier', id)?.defaultAdapter ?? 'none';
      return n;
    });
    if (g === 'carrier' || g === 'adapter') setEdits((e) => { const { mount_rot, beam_x, ...rest } = e; return rest; });
    setActive(g); setSolo(false);
  }, []);

  // Config rail: look at that group in the assembly and show its cards; the same button again closes them.
  const onPick = useCallback((g: string) => {
    setConfigOpen((o) => !(o && active === g && !solo));
    setActive(g); setSolo(false);
  }, [active, solo]);
  // Selection bar: that part alone; the same chip again goes back to the assembly, still looking at it.
  const onSolo = useCallback((g: string) => {
    setSolo(!(solo && active === g));
    setActive(g); setConfigOpen(false);
  }, [active, solo]);
  const onOverall = useCallback(() => { setActive('overall'); setSolo(false); setConfigOpen(false); }, []);

  const presets: Preset[] | undefined = useMemo(() => custom && direct
    ? Object.values(FLANGES).map((f) => ({ label: tx(f.label, lang), sets: f.sets }))
    : undefined, [custom, direct, lang]);
  const onApplyPreset = useCallback((pr: Preset) => setEdits((e) => ({ ...e, ...pr.sets })), []);

  const exporters: Exporter[] = useMemo(() => {
    if (!config) return [];
    const ex: Exporter[] = [];
    for (const name of Object.keys(config.print_sets ?? {})) ex.push({ kind: 'set', name, label: t('exPrint', { name }), hint: t('exPrintHint') });
    ex.push({ kind: 'config', name: 'config', label: t('exConfig'), hint: t('exConfigHint') });
    for (const p of config.parts ?? []) if (p.role === 'printed') ex.push({ kind: 'part', name: p.name, label: t('exPart', { name: p.name }), hint: t('exPartHint') });
    return ex;
  }, [config, t]);

  const onExport = useCallback(async (e: Exporter) => {
    if (!result || !engine.current) return;
    // the phone joins the name only when it is not the default one, so the usual downloads keep their names
    const phoneTag = camera && camera.id !== DEFAULT_SELECTION.camera ? `_${camera.id}` : '';
    const tag = `${carrier?.id ?? 'custom'}_${adapter?.id ?? 'none'}${phoneTag}`;
    if (e.kind === 'config') {
      const c = { ...result.config, name: `${result.config.name ?? 'ipush'}_${tag}` };
      download(`ipush_${tag}.json`, JSON.stringify(c, null, 1), 'application/json');
      return;
    }
    setExporting(e.kind + e.name);
    try {
      const s = await engine.current.stl(e.kind, e.name);
      download(`${s.file.replace(/\.stl$/, '')}_${tag}.stl`, s.bytes, 'model/stl');
    } catch (err: any) { setError(t('exportFailed') + (err?.message || err)); }
    setExporting(null);
  }, [result, carrier, adapter, camera, t]);

  const sel = GROUPS.map((g) => ({ group: g, item: item(g.id, selection[g.id]) }));
  const group = active === 'overall' ? null : GROUPS.find((g) => g.id === active) ?? null;
  const view = ((solo && group?.view) || 'overall') as SceneContent['view'];
  const joint = direct ? carrier?.direct?.joint : undefined;
  const content = useMemo<SceneContent>(() => ({ view, focus: active, carrier, adapter, joint, mountRot: defaults.mount_rot, result, lang }), [view, active, carrier, adapter, joint, defaults, result, lang]);

  const status = engineState === 'loading' ? { text: t('loadingEngine'), kind: 'busy' as const }
    : engineState === 'error' ? { text: t('engineFailed') + error, kind: 'danger' as const }
    : error ? { text: t('solveFailed') + error, kind: 'danger' as const }
    : busy ? { text: t('updating'), kind: 'busy' as const }
    : result?.checks.length ? { text: t('checksFailed', { n: result.checks.length }), kind: 'warn' as const }
    : result ? { text: t('updated', { ms: Math.round(result.ms.python + result.ms.geometry) }), kind: 'ok' as const }
    : { text: '…', kind: 'busy' as const };

  // Only what must be fixed is drawn over the view. Notes that block nothing (result.warnings, e.g. a flange screw
  // that needs a short hex key) are assembly information: they are listed with the flange adapter in Inspect.
  const alerts = [
    ...(error && engineState === 'ready' ? [{ text: t('solveFailed') + error, kind: 'danger' as const }] : []),
    ...(result?.checks ?? []).map((c) => ({ text: c, kind: 'warn' as const })),
  ];

  // parameters that differ from the defaults right now (edits of values the adapter or flange fixes do not count)
  const nEdits = Object.keys(edits).filter((k) => !isLocked(k, fixed, custom)).length;

  const showParams = active === 'pusher' || active === 'overall' || active === 'adapter' || (active === 'carrier' && custom);

  return (
    <LangContext.Provider value={lang}>
    <div ref={rootRef} className="editor" style={{ '--free-r': `${insets.r}px` } as React.CSSProperties}>
      <CenterPanel content={content} insets={insets} status={status} alerts={alerts}
        resetKey={resetKey} onResetView={() => setResetKey((k) => k + 1)} edited={nEdits} onResetParams={() => setEdits({})} />
      <header className="topbar">
        <div className="topbar-side">
          <div className="brand-pill float">
            <a className="brand" href={langPath(lang)}><Logo size={24} /><span>{PRODUCT[lang]}</span></a>
            <span className="crumb">{t('editorTitle')}</span>
          </div>
        </div>
        <SelectionBar selection={sel} solo={solo && group ? group.id : null} onSolo={onSolo} onOverall={onOverall} />
        <div className="topbar-side end">
          <a className="docs-link float" href={langPath(lang, 'docs/')}>{t('docs')}</a>
          <div className="theme-switch float" role="radiogroup" aria-label={t('theme')}>
            {THEMES.map((th) => {
              const label = t(th === 'system' ? 'themeSystem' : th === 'light' ? 'themeLight' : 'themeDark');
              return (
                <button key={th} className={'icon-btn' + (th === theme ? ' on' : '')} role="radio" aria-checked={th === theme}
                  aria-label={label} title={`${t('theme')}: ${label}`} onClick={() => pickTheme(th)}>
                  <Ico name={`theme-${th}`} size={18} />
                </button>
              );
            })}
          </div>
          <nav className="lang-switch float" aria-label="Language">
            {LANGS.map((l) => l === lang
              ? <span key={l} className="on" aria-current="true">{LANG_LABEL[l]}</span>
              : <a key={l} href={langPath(l, 'editor')} hrefLang={l} lang={l}>{LANG_LABEL[l]}</a>)}
          </nav>
        </div>
      </header>
      <LeftPanel selection={selection} active={active} open={configOpen && !solo} onPick={onPick} onClose={() => setConfigOpen(false)} onSelect={onSelect} />
      {!inspectOpen && (
        <button className="inspect-tab float" onClick={() => setInspectOpen(true)} aria-expanded={false}>
          <Ico name="sliders" size={18} />{t('inspect')}
        </button>
      )}
      {inspectOpen && (
      <aside ref={inspectRef} className={'right float' + (showParams ? ' with-params' : '')} style={{ '--split': `${split * 100}%` } as React.CSSProperties}>
        <button className="icon-btn inspect-close" title={t('closePanel')} aria-label={t('closePanel')} onClick={() => setInspectOpen(false)}><Ico name="close" size={18} /></button>
        <InfoPanel group={group} it={group ? item(group.id, selection[group.id]) : undefined} selection={sel} result={result} carrier={carrier} joint={joint} />
        {showParams && (
          <div className="splitter" role="separator" aria-orientation="horizontal" tabIndex={0}
            aria-valuemin={Math.round(SPLIT_MIN * 100)} aria-valuemax={Math.round(SPLIT_MAX * 100)} aria-valuenow={Math.round(split * 100)}
            title={t('dragSplit')}
            onPointerDown={(e) => {
              const el = e.currentTarget; el.setPointerCapture(e.pointerId);
              const box = inspectRef.current!.getBoundingClientRect();
              const move = (ev: PointerEvent) => setSplit(clampSplit((ev.clientY - box.top) / box.height));
              const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); };
              el.addEventListener('pointermove', move); el.addEventListener('pointerup', up);
            }}
            onDoubleClick={() => setSplit(SPLIT_DEFAULT)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowUp') { e.preventDefault(); setSplit((f) => clampSplit(f - 0.02)); }
              if (e.key === 'ArrowDown') { e.preventDefault(); setSplit((f) => clampSplit(f + 0.02)); }
            }} />
        )}
        {showParams ? (
          <ParamsPanel config={config} result={result} edits={edits} fixed={fixed} customFlange={custom} onChange={onChange} presets={presets} onApplyPreset={onApplyPreset}
            onResetAll={() => setEdits({})} exporters={exporters} onExport={onExport} exporting={exporting} error={error} />
        ) : (
          <section className="params empty">
            <h2>{t('params')}</h2>
            <p className="mute">{t(group?.id === 'carrier' ? 'noParamsCarrier' : group?.id === 'camera' ? 'noParamsCamera' : 'noParams')}</p>
            <button className="btn" onClick={() => setActive('pusher')}>{t('goPusher')}</button>
          </section>
        )}
      </aside>
      )}
      <div className="narrow-note">{t('narrow')}</div>
    </div>
    </LangContext.Provider>
  );
}
