// Right column, top: fixed facts about the selected item (not editable).
import type { CatalogItem, Group, InfoRow, JointTurn } from '../data/catalog';
import type { Pose, SolveResult } from '../engine/types';
import { FlangeDrawing } from './FlangeDrawing';
import { Ico } from './icons';
import { useI18n, makeT } from '../i18n';
import { basePatternSpec, customFlangeSpec } from '../data/flanges';

const PLA = 1.24; // g/cm³

function Rows({ rows }: { rows: InfoRow[] }) {
  const { t, tx } = useI18n();
  return (
    <dl className="rows">
      {rows.map((r) => (
        <div key={tx(r.label)} className="row">
          <dt>{tx(r.label)}</dt>
          <dd>{tx(r.value)}{r.verify && <span className="badge warn">{t('verify')}</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

function Links({ it }: { it: CatalogItem }) {
  const { tx } = useI18n();
  if (!it.links?.length) return null;
  return (
    <ul className="links">
      {it.links.map((l) => (
        <li key={l.url}><a href={l.url} target="_blank" rel="noreferrer">{tx(l.label)}<Ico name="link" size={12} /></a></li>
      ))}
    </ul>
  );
}

const fmt = (v: number, d = 1) => (Number.isFinite(v) ? v.toFixed(d) : '—');
const vec = (p: number[]) => p.map((v) => fmt(v)).join(', ');

/** Position of `p` (root frame) seen from frame `f` (root frame pose, quat [w, x, y, z]). */
function inFrame(p: number[], f: Pose): number[] {
  const [w, x, y, z] = f.quat, d = [p[0] - f.pos[0], p[1] - f.pos[1], p[2] - f.pos[2]];
  // rotate d by the conjugate quaternion: d + 2 q × (q × d − w d), with q = −(x, y, z)
  const q = [-x, -y, -z];
  const c1 = [q[1] * d[2] - q[2] * d[1] + w * d[0], q[2] * d[0] - q[0] * d[2] + w * d[1], q[0] * d[1] - q[1] * d[0] + w * d[2]];
  return [d[0] + 2 * (q[1] * c1[2] - q[2] * c1[1]), d[1] + 2 * (q[2] * c1[0] - q[0] * c1[2]), d[2] + 2 * (q[0] * c1[1] - q[1] * c1[0])];
}

function live(result: SolveResult | null, t: ReturnType<typeof makeT>) {
  if (!result) return [];
  const R = result.resolved;
  const printed = result.meshes.filter((m) => m.role === 'printed');
  const vol = printed.reduce((s, m) => s + m.volume, 0);
  const rows: InfoRow[] = printed.map((m) => ({ label: t('volume', { name: m.name }), value: `${fmt(m.volume / 1000)} cm³` }));
  rows.push({ label: t('mass'), value: `${fmt((vol / 1000) * PLA)} g` });
  const Fm = R.frames.F_mount?.world;
  if (R.frames.T_tcp && Fm) rows.push({ label: t('tcpInMount'), value: `${vec(inFrame(R.frames.T_tcp.world.pos, Fm))} mm` });
  if (R.frames.T_tcp) rows.push({ label: t('tcpInFlange'), value: `${vec(R.frames.T_tcp.world.pos)} mm` });
  if (R.frames.C_main) rows.push({ label: t('camInFlange'), value: `${vec(R.frames.C_main.world.pos)} mm` });
  return rows;
}

interface Props {
  group: Group | null;          // null = overall
  it?: CatalogItem;
  selection: { group: Group; item?: CatalogItem }[];
  result: SolveResult | null;
  carrier?: CatalogItem;
  joint?: JointTurn;
}

export function InfoPanel({ group, it, selection, result, carrier, joint }: Props) {
  const { t, tx } = useI18n();
  if (!group) {
    return (
      <section className="info">
        <h2>{t('overallTitle')}</h2>
        <dl className="rows">
          {selection.map(({ group: g, item: i }) => (
            <div key={g.id} className="row"><dt>{tx(g.title)}</dt><dd>{i ? tx(i.name) : '—'}</dd></div>
          ))}
        </dl>
        <h3>{t('currentPusher')}</h3>
        <Rows rows={live(result, t)} />
      </section>
    );
  }
  if (!it) return <section className="info"><h2>{tx(group.title)}</h2><p className="mute">{t('notSelected')}</p></section>;
  const cam = result?.resolved.cameras?.C_main;
  const flange = it.flange ?? (it.customFlange && result ? customFlangeSpec(result.resolved.params) : undefined);
  const P = result?.resolved.params;
  const base = group.view === 'adapter' && P ? basePatternSpec(P) : null;
  return (
    <section className="info">
      <h2>{tx(it.name)}{it.subtitle && <small>{tx(it.subtitle)}</small>}</h2>
      {group.view === 'carrier' && flange && (
        <div className="flange-block">
          <h3>{t('flangePattern')} · {tx(flange.title)}</h3>
          <FlangeDrawing spec={flange} />
          <dl className="rows strong">
            <div className="row"><dt>{t('screws')}</dt><dd>{tx(flange.screws)}</dd></div>
            <div className="row"><dt>{t('threads')}</dt><dd>{t('threadsVal', { n: flange.holes, t: flange.thread, pcd: flange.pcd })}</dd></div>
            <div className="row"><dt>{t('threadDepth')}</dt><dd>{tx(flange.threadDepth)}{flange.threadDepthVerify && <span className="badge warn">{t('verify')}</span>}</dd></div>
            {flange.pilot && <div className="row"><dt>{t('pilot')}</dt><dd>Ø{flange.pilot.d} {flange.pilot.fit}</dd></div>}
            {flange.pin && <div className="row"><dt>{t('pin')}</dt><dd>Ø{flange.pin.d} {flange.pin.fit}</dd></div>}
          </dl>
          {flange.note && <p className="note">{tx(flange.note)}</p>}
          <p className="note mute">{t('source')}{tx(flange.source)}</p>
        </div>
      )}
      {group.view === 'adapter' && P && (
        <div className="flange-block">
          <h3>{t('basePattern')}</h3>
          {base ? <FlangeDrawing spec={base} /> : <p className="note">{t('baseNoScrews')}</p>}
          <dl className="rows strong">
            {base && <div className="row"><dt>{t('screws')}</dt><dd>{tx(base.screws)}</dd></div>}
            <div className="row"><dt>{t('adapterHeight')}</dt><dd>{fmt(P.adapter_h)} mm</dd></div>
            <div className="row"><dt>{t('mountAngle')}</dt><dd>{fmt(P.mount_rot, 0)}°{carrier?.mountRot !== undefined && <span className="mute"> · {t('mountAngleDefault', { name: tx(carrier.name), deg: carrier.mountRot })}</span>}</dd></div>
            {joint && <div className="row"><dt>{t('jointTurn')}</dt><dd>{t('jointTurnVal', { joint: joint.name, deg: joint.deg })}</dd></div>}
            {/* notes that block nothing, without the rule id and volume at the end */}
            {(result?.warnings ?? []).map((w) => <div key={w} className="row"><dt>{t('mountNote')}</dt><dd>{w.replace(/\s*\([\w-]+: [\d.]+ mm³\)$/, '')}</dd></div>)}
          </dl>
          <p className="note mute">{t('basePatternNote')}</p>
        </div>
      )}
      {it.info && <Rows rows={it.info} />}
      {group.view === 'camera' && cam && (
        <>
          <h3>{t('camInModel')}</h3>
          <Rows rows={[
            { label: t('vfov'), value: `${fmt(cam.fovy_deg)}°` },
            { label: t('frame'), value: `${cam.resolution?.join(' × ')} (${fmt(cam.aspect, 3)})` },
            { label: t('lensToTcp'), value: `${fmt(result!.resolved.params.distance)} mm` },
          ]} />
        </>
      )}
      {group.view === 'pusher' && <><h3>{t('fromParams')}</h3><Rows rows={live(result, t)} /></>}
      <Links it={it} />
    </section>
  );
}
