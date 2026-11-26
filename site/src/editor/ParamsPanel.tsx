// Right column, bottom: the pusher parameters. Values come from the config; edits are kept separately so
// "Reset" is always exact. Parameters fixed by another group (carrier, adapter, camera, tip) are shown read-only.
import { useEffect, useState } from 'react';
import { SECTIONS, paramMeta as meta, isLocked } from '../data/pusherParams';
import { GROUPS } from '../data/catalog';
import { useI18n } from '../i18n';
import type { ParamValue, SolveResult } from '../engine/types';
import { Ico } from './icons';


function NumberField({ value, onCommit, step, disabled }: { value: number; onCommit: (v: number) => void; step?: number; disabled?: boolean }) {
  const shown = Number.isFinite(value) ? +value.toFixed(4) + '' : '';
  const [draft, setDraft] = useState<string | null>(null);
  useEffect(() => setDraft(null), [value]);
  const commit = (s: string) => { const v = Number(s); if (s.trim() !== '' && Number.isFinite(v)) onCommit(v); else setDraft(null); };
  return (
    <input className="num" type="text" inputMode="decimal" disabled={disabled} value={draft ?? shown} step={step}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setDraft(null); }} />
  );
}

export interface Preset { label: string; sets: Record<string, number> }

export interface Exporter { kind: 'config' | 'set' | 'part'; name: string; label: string; hint: string }

interface Props {
  config: any | null;
  result: SolveResult | null;
  edits: Record<string, ParamValue>;
  fixed: Record<string, { value: number; by: string }>;   // params decided by another group
  customFlange: boolean;                                  // the carrier's flange values are editable
  onChange: (k: string, v: number | undefined) => void;
  presets?: Preset[];                                     // starting points for the custom flange
  onApplyPreset?: (p: Preset) => void;
  onResetAll: () => void;
  exporters: Exporter[];
  onExport: (e: Exporter) => void;
  exporting: string | null;
  error: string | null;
}

export function ParamsPanel(p: Props) {
  const { t, tx } = useI18n();
  const [advanced, setAdvanced] = useState(false);
  if (!p.config) return <section className="params"><p className="mute">{t('loadingConfig')}</p></section>;
  const names = Object.keys(p.config.params);
  const vals = p.result?.resolved.params ?? {};
  const bySection = new Map<string, string[]>();
  for (const k of names) {
    const m = meta(k);
    // carrier-owned values are editable on a custom flange, unless the adapter fixes them
    const locked = isLocked(k, p.fixed, p.customFlange);
    const sec = locked ? 'owned' : m.section;
    if (m.advanced && !advanced && !locked) continue;
    bySection.set(sec, [...(bySection.get(sec) ?? []), k]);
  }
  const nEdits = Object.keys(p.edits).length;
  const checks = p.result?.checks ?? [];
  const blocked = checks.length > 0 || !!p.error;

  return (
    <section className="params">
      <div className="params-head">
        <h2>{t('pusherParams')}</h2>
        <label className="chk"><input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />{t('advanced')}</label>
        <button className="btn ghost sm" disabled={!nEdits} onClick={p.onResetAll} title={t('resetAllHint')}>
          <Ico name="reset" size={14} />{t('resetAll')}{nEdits ? ` (${nEdits})` : ''}
        </button>
      </div>

      {/* failed checks are shown over the 3D view (CenterPanel), so this column never shifts while dragging */}

      {SECTIONS.map(({ id: sec, title }) => {
        const ks = bySection.get(sec);
        if (!ks?.length) return null;
        const ro = sec === 'owned';
        const body = ks.map((k) => {
          const m = meta(k);
          const fixedBy = p.fixed[k];
          const src = p.config.params[k];
          const v = fixedBy ? fixedBy.value : (typeof p.edits[k] === 'number' ? (p.edits[k] as number) : vals[k]);
          const changed = k in p.edits;
          const expr = !changed && typeof src === 'string';
          return (
            <div key={k} className={'param' + (changed ? ' changed' : '') + (ro ? ' ro' : '')}>
              <div className="param-top">
                <label title={k}>{tx(m.label)}<code>{k}</code></label>
                {ro ? <span className="ro-val">{Number.isFinite(v) ? +(+v).toFixed(3) : '—'} {m.unit}</span> : (
                  <span className="param-val">
                    <NumberField value={v} step={m.step} onCommit={(x) => p.onChange(k, x)} />
                    <span className="unit">{m.unit}</span>
                    <button className="icon-btn xs" title={t('resetOne')} disabled={!changed} onClick={() => p.onChange(k, undefined)}><Ico name="reset" size={12} /></button>
                  </span>
                )}
              </div>
              {!ro && m.slider && m.min !== undefined && m.max !== undefined && (
                <input type="range" min={m.min} max={m.max} step={m.step ?? 0.1} value={Number.isFinite(v) ? v : m.min}
                  onChange={(e) => p.onChange(k, Number(e.target.value))} />
              )}
              {(m.hint || expr || ro) && (
                <div className="param-hint">
                  {ro && t('decidedBy', { who: fixedBy ? fixedBy.by : tx(GROUPS.find((g) => g.id === m.owner)?.title) || '—' })}
                  {ro && (m.hint || expr) ? ' · ' : ''}
                  {expr && <>= <code>{src}</code>{m.hint ? ' · ' : ''}</>}
                  {tx(m.hint)}
                </div>
              )}
            </div>
          );
        });
        return ro ? (
          <details key={sec} className="section">
            <summary>{tx(title)}<span className="mute"> ({ks.length}, {t('readOnly')})</span></summary>{body}
          </details>
        ) : (
          <div key={sec} className="section"><h3>{tx(title)}</h3>
            {sec === 'flange' && p.presets?.length ? (
              <div className="presets"><span className="mute">{t('startFrom')}</span>
                {p.presets.map((pr) => <button key={pr.label} className="btn sm" onClick={() => p.onApplyPreset?.(pr)}>{pr.label}</button>)}
              </div>
            ) : null}
            {body}</div>
        );
      })}

      <div className="export">
        <h3>{t('export')}</h3>
        <div className="export-btns">
          {p.exporters.map((e) => (
            <button key={e.kind + e.name} className={'btn' + (e.kind === 'set' ? ' primary' : '')} title={e.hint}
              disabled={(blocked && e.kind !== 'config') || !p.result || p.exporting !== null} onClick={() => p.onExport(e)}>
              <Ico name="download" size={14} />{p.exporting === e.kind + e.name ? t('generating') : e.label}
            </button>
          ))}
        </div>
        <p className="note mute">{t('exportNote').split('`').map((x, i) => (i % 2 ? <code key={i}>{x}</code> : x))}</p>
        <p className="note mute">{t('localOnly')}</p>
      </div>
    </section>
  );
}
