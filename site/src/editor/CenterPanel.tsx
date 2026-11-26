// View: the 3D view fills the window (CenterPanel); what is selected sits in the top strip (SelectionBar).
// The view shows the full assembly and travels to the group being configured; a chip of the selection bar
// shows that part alone.
import { useEffect, useLayoutEffect, useRef } from 'react';
import type { CatalogItem, Group } from '../data/catalog';
import { SceneView, ARM_MODELS, type SceneContent } from './scene';
import { Ico } from './icons';
import { useI18n, type UIKey } from '../i18n';
import { onThemeChange } from '../theme';

const VIEW_NOTE: Record<SceneContent['view'], UIKey> = {
  carrier: 'noteCarrier', adapter: 'noteAdapter', pusher: 'notePusher', tip: 'noteTip', camera: 'noteCamera', overall: 'noteOverall',
};

/** What the floating pieces cover on each side of the view, px. */
export interface Insets { l: number; r: number; t: number; b: number }

function Viewport({ content, resetKey, insets }: { content: SceneContent; resetKey: number; insets: Insets }) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<SceneView | null>(null);
  useEffect(() => {
    view.current = new SceneView(host.current!);
    return () => { view.current?.dispose(); view.current = null; };
  }, []);
  // before the content update below, so a new framing already knows what the panels cover
  useLayoutEffect(() => { view.current?.setInsets(insets.l, insets.r, insets.t, insets.b); }, [insets.l, insets.r, insets.t, insets.b]);
  useEffect(() => { view.current?.setInsets(insets.l, insets.r, insets.t, insets.b); view.current?.update(content); }, [content]);
  useEffect(() => { if (resetKey) { view.current?.resetView(); view.current?.update(content); } }, [resetKey]);
  useEffect(() => onThemeChange(() => view.current?.retheme()), []);
  return <div className="viewport-canvas" ref={host} />;
}

interface BarProps {
  selection: { group: Group; item?: CatalogItem }[];
  solo: string | null;                 // the group shown alone, if any
  onSolo: (g: string) => void;         // a chip: show that part alone (again = back to the assembly)
  onOverall: () => void;
}

export function SelectionBar(p: BarProps) {
  const { t, tx } = useI18n();
  return (
    <div className="summary float">
      <div className="chips">
        {p.selection.map(({ group, item }) => {
          const on = p.solo === group.id;
          return (
            <button key={group.id} className={'chip' + (on ? ' on' : '')} aria-pressed={on}
              title={`${tx(group.title)}: ${item ? tx(item.name) : t('none')} · ${t(on ? 'soloBack' : 'soloHint')}`} onClick={() => p.onSolo(group.id)}>
              {item && <Ico name={item.icon} size={22} />}
              <span><small>{tx(group.title)}</small>{item ? tx(item.name) : t('none')}</span>
            </button>
          );
        })}
      </div>
      <button className={'btn overall' + (p.solo ? '' : ' primary')} onClick={p.onOverall}>
        <Ico name="overall" size={16} />{t('overall')}
      </button>
    </div>
  );
}

interface Props {
  content: SceneContent;
  insets: Insets;
  status: { text: string; kind: 'busy' | 'ok' | 'warn' | 'danger' };
  alerts: { text: string; kind: 'warn' | 'danger' | 'note' }[];   // failed checks and notes, drawn over the view
  resetKey: number;
  onResetView: () => void;
  edited: number;                // parameters changed from the defaults; said in the view because Inspect may be closed
  onResetParams: () => void;
}

export function CenterPanel(p: Props) {
  const { t } = useI18n();
  const c = p.content;
  const solo = c.view !== 'overall';
  const arm = c.view === 'carrier' && c.carrier ? ARM_MODELS[c.carrier.id] : undefined;
  const custom = c.view === 'carrier' && c.carrier?.customFlange;
  const j = c.joint;
  const turned = j && (c.view === 'carrier' || (!solo && c.focus === 'carrier')) ? t('noteJoint', { joint: j.name, deg: j.deg }) : '';
  // what a part shown alone is drawn with; the assembly needs no caption
  const note = [solo ? (custom ? t('noteCustom') : arm ? t('noteArm', { src: arm.short, pose: arm.pose }) : t(VIEW_NOTE[c.view])) : '', turned].filter(Boolean).join(' · ');
  return (
    <main className="stage">
      <Viewport content={c} resetKey={p.resetKey} insets={p.insets} />
      {p.alerts.length > 0 && (
        <div className="vp-alerts" role="status">
          {p.alerts.map((a) => <div key={a.text} className={'alert ' + a.kind}><Ico name="warn" size={16} /><span>{a.text}</span></div>)}
        </div>
      )}
      <div className="vp-bottom">
        <span className={'status ' + p.status.kind}>{p.status.text}</span>
        {p.edited > 0 && (
          <button className="btn sm edited" onClick={p.onResetParams} title={t('resetAllHint')}>
            <Ico name="reset" size={14} />{t('editedReset', { n: p.edited })}
          </button>
        )}
        {note ? <span className="vp-note" title={note}>{note}</span> : <span className="spacer" />}
        <button className="btn sm ghost" onClick={p.onResetView} title={t('resetView')}><Ico name="reset" size={14} />{t('view')}</button>
        <span className="legend"><i className="x" />X<i className="y" />Y<i className="z" />Z · {t('units')}</span>
      </div>
    </main>
  );
}
