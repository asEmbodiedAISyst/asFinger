// 2D drawing of a robot flange face, seen from the tool side (looking at the flange). Units mm, drawn to scale.
import type { FlangeSpec } from '../data/catalog';
import { holeAngles } from '../data/flanges';
import { useI18n } from '../i18n';

export function FlangeDrawing({ spec }: { spec: FlangeSpec }) {
  const { t, tx } = useI18n();
  const outerR = (spec.outerD ?? spec.pcd + 18) / 2;
  const S = 260, pad = 26, k = (S / 2 - pad) / outerR;   // px per mm
  const c = S / 2;
  const X = (x: number) => c + x * k, Y = (y: number) => c - y * k;
  const holeR = (parseFloat(spec.thread.replace(/[^0-9.]/g, '')) || 4) / 2;
  const holes = holeAngles(spec).map((deg) => {
    const a = (deg * Math.PI) / 180;
    return [(spec.pcd / 2) * Math.cos(a), (spec.pcd / 2) * Math.sin(a)] as const;
  });
  const a0 = (spec.firstHoleDeg * Math.PI) / 180;
  const arcR = spec.pcd / 2 * 0.42;
  return (
    <figure className="flange">
      <svg viewBox={`0 0 ${S} ${S}`} width="100%" role="img" aria-label={`${t('flangePattern')} ${tx(spec.title)}`}>
        <circle cx={c} cy={c} r={outerR * k} className="fl-outer" />
        {spec.pilot && <circle cx={c} cy={c} r={(spec.pilot.d / 2) * k} className="fl-edge" />}
        <circle cx={c} cy={c} r={(spec.pcd / 2) * k} className="fl-center" />
        <line x1={X(-outerR - 4)} y1={c} x2={X(outerR + 4)} y2={c} className="fl-center" />
        <line x1={c} y1={Y(-outerR - 4)} x2={c} y2={Y(outerR + 4)} className="fl-center" />
        {holes.map(([x, y], i) => (
          <g key={i}>
            <circle cx={X(x)} cy={Y(y)} r={holeR * k} className="fl-hole" />
            <circle cx={X(x)} cy={Y(y)} r={holeR * 0.82 * k} className="fl-thread" />
          </g>
        ))}
        {spec.pin && (() => {
          const a = (spec.pin.deg * Math.PI) / 180, x = (spec.pin.pcd / 2) * Math.cos(a), y = (spec.pin.pcd / 2) * Math.sin(a);
          return <circle cx={X(x)} cy={Y(y)} r={(spec.pin.d / 2) * k} className="fl-pin" />;
        })()}
        {/* angle of the first hole from +X */}
        {spec.firstHoleDeg !== 0 && (
          <>
            <path d={`M ${X(arcR)} ${c} A ${arcR * k} ${arcR * k} 0 0 0 ${X(arcR * Math.cos(a0))} ${Y(arcR * Math.sin(a0))}`} className="fl-dim" />
            <line x1={c} y1={c} x2={X(holes[0][0])} y2={Y(holes[0][1])} className="fl-dim" />
            <text x={X(arcR * 1.15 * Math.cos(a0 / 2))} y={Y(arcR * 1.15 * Math.sin(a0 / 2))} className="fl-txt" dominantBaseline="middle">{spec.firstHoleDeg}°</text>
          </>
        )}
        {/* axes */}
        <g className="fl-axis-x"><line x1={c} y1={c} x2={c + 34} y2={c} /><text x={c + 38} y={c + 4}>X</text></g>
        <g className="fl-axis-y"><line x1={c} y1={c} x2={c} y2={c - 34} /><text x={c - 4} y={c - 38}>Y</text></g>
        <text x={X(holes[0][0]) - holeR * k - 3} y={Y(holes[0][1]) - holeR * k - 3} textAnchor="end" className="fl-txt">{spec.holes}× {spec.thread}</text>
        <text x={c} y={S - 6} textAnchor="middle" className="fl-txt">{t('pcd', { pcd: spec.pcd })}{spec.outerD ? ` · ${t('outer', { d: spec.outerD })}` : ''}</text>
        {spec.pilot && <text x={c} y={Y(-(spec.pilot.d / 2)) + 12} textAnchor="middle" className="fl-txt mute">Ø{spec.pilot.d} {spec.pilot.fit}</text>}
      </svg>
      <figcaption>{t('flangeCaption')}</figcaption>
    </figure>
  );
}
