// Line icons in the same style as the logo: 48 grid, currentColor stroke, round caps. One per catalog `icon`.
import type { ReactElement } from 'react';
import type { Icon } from '../data/catalog';
import { PRODUCT } from '../i18n';

const P: Record<Icon | 'chevron' | 'panel' | 'overall' | 'reset' | 'download' | 'warn' | 'link' | 'sliders' | 'close' | 'theme-system' | 'theme-light' | 'theme-dark', ReactElement> = {
  arm6: (<>
    <path d="M10 40h16" /><path d="M14 40v-5h8v5" /><path d="M18 35V25" /><circle cx="18" cy="23" r="2.5" />
    <path d="M20 21.5 31 13" /><circle cx="33" cy="11.5" r="2.5" /><path d="M34.5 13.5 37 22" /><path d="M33.5 22h7" /><path d="M37 22v4" />
  </>),
  arm7: (<>
    <path d="M10 40h16" /><path d="M14 40v-5h8v5" /><path d="M18 35V27" /><circle cx="18" cy="25" r="2.5" />
    <path d="M18 22.5v-6" /><circle cx="18" cy="14" r="2.5" /><path d="M20.5 13H31" /><circle cx="33.5" cy="13" r="2.5" />
    <path d="M35 15.2 37.5 22" /><path d="M34 22h7" /><path d="M37.5 22v4" />
  </>),
  hand: (<>
    <path d="M19 26V11a3 3 0 0 1 6 0v12" /><path d="M25 23v-1a3 3 0 0 1 6 0v2" /><path d="M31 24a3 3 0 0 1 6 0v4" />
    <path d="M37 28v3.5c0 5-3.3 8.5-8 8.5h-6c-4.7 0-10-4-10-10v-1.7c0-2.3 2-3.6 4.3-3" />
  </>),
  rod: (<>
    <path d="M12 10h14v6H12z" /><path d="M19 16l-5 18" /><path d="M23 16l-5 18" /><path d="M14 34a2.1 2.1 0 0 0 4 0" />
    <path d="M26 13l8 4" /><path d="M31 15.5 36 34" /><path d="M33 14l6 22" /><path d="M36 34l3 2" />
  </>),
  'rod-arc': (<>
    <path d="M12 10h14v6H12z" /><path d="M19 16l-3 16" /><path d="M23 16l-3 16" /><path d="M10 34c3-3 9-3 12 0" />
  </>),
  'rod-square': (<>
    <path d="M12 10h14v6H12z" /><path d="M17 16l-4 18" /><path d="M25 16l-4 18" /><path d="M13 34h8" />
    <path d="M26 13l8 4" /><path d="M31 15.5 36 34" /><path d="M33 14l6 22" /><path d="M36 34l3 2" />
  </>),
  humanoid: (<>
    <circle cx="24" cy="9.5" r="3.5" /><path d="M18 15h12l1 13h-3l-1 12h-6l-1-12h-3z" /><path d="M18 16l-6 11" /><path d="M30 16l6 11" />
    <path d="M22 28v12M26 28v12" />
  </>),
  'camera-none': (<>
    <rect x="8" y="15" width="32" height="18" rx="3.5" strokeDasharray="2.4 2.8" /><path d="M14 38 34 10" />
  </>),
  'tip-ball': (<>
    <path d="M18 8v20" /><path d="M30 8v20" /><path d="M18 28a6 6 0 0 0 12 0" /><path d="M10 40h28" /><circle cx="24" cy="34" r="0.8" />
  </>),
  'tip-sensor': (<>
    <path d="M18 8v18" /><path d="M30 8v18" /><path d="M15 26h18v4a9 9 0 0 1-18 0z" /><path d="M19 31h2M23 31h2M27 31h2" /><path d="M21 35h2M25 35h2" />
  </>),
  'tip-surface': (<>
    <path d="M18 8v18" /><path d="M30 8v18" /><path d="M18 26a6 6 0 0 0 12 0" /><path d="M15.5 27a8.5 8.5 0 0 0 17 0" strokeDasharray="2 2.4" />
  </>),
  phone: (<>
    <rect x="8" y="15" width="32" height="18" rx="3.5" /><circle cx="14" cy="20.5" r="2.4" /><circle cx="14" cy="27.5" r="2.4" />
    <circle cx="19.5" cy="24" r="2.4" /><path d="M36 21v6" />
  </>),
  flange: (<>
    <circle cx="24" cy="24" r="15" /><circle cx="24" cy="24" r="6" strokeDasharray="2 2.4" />
    <circle cx="15.5" cy="15.5" r="2" /><circle cx="32.5" cy="15.5" r="2" /><circle cx="15.5" cy="32.5" r="2" /><circle cx="32.5" cy="32.5" r="2" />
  </>),
  // flange adapter: robot flange (bottom bar) and pusher base (top bar), seen from the side
  'adapter-none': (<>
    <path d="M10 30h28" /><path d="M10 30v6h28v-6" strokeDasharray="2 2.6" /><path d="M10 30v-8h28v8" /><path d="M17 22v8M31 22v8" /><path d="M22 22 26 10M30 22 34 10" />
  </>),
  'adapter-ab': (<>
    <path d="M9 38h30" strokeDasharray="2 2.6" /><path d="M15 38v-6h18v6" /><path d="M9 34v-8h30v8" /><path d="M9 30H5M39 30h4" /><path d="M9 26v-6h30v6" /><path d="M15 20v6M33 20v6" /><path d="M22 20 25 9M29 20 32 9" />
  </>),
  'adapter-fused': (<>
    <path d="M9 38h30" strokeDasharray="2 2.6" /><path d="M15 38v-6h18v6" /><path d="M9 34V20h30v14" /><path d="M9 30H5M39 30h4" /><path d="M22 20 25 9M29 20 32 9" />
  </>),
  // a ring clamped round a wrist (left), the pusher base on its tool side (right)
  'adapter-wrist': (<>
    <path d="M6 18h10v12H6" strokeDasharray="2 2.6" /><path d="M16 14h10v20H16z" /><path d="M21 14v-3M21 34v3" /><path d="M26 18h6v12h-6" /><path d="M32 21 42 13M32 27l10-8" />
  </>),
  depthcam: (<>
    <rect x="6" y="18" width="36" height="12" rx="6" /><circle cx="14" cy="24" r="2.5" /><circle cx="24" cy="24" r="2" /><circle cx="34" cy="24" r="2.5" />
  </>),
  chevron: <path d="M18 20l6 6 6-6" />,
  panel: (<><rect x="8" y="10" width="32" height="28" rx="4" /><path d="M19 10v28" /></>),
  overall: (<><path d="M24 8 38 16v16l-14 8-14-8V16z" /><path d="M10 16l14 8 14-8" /><path d="M24 24v16" /></>),
  reset: (<><path d="M14 16a13 13 0 1 1-3 9" /><path d="M10 10v7h7" /></>),
  download: (<><path d="M24 9v20" /><path d="M16 21l8 8 8-8" /><path d="M11 37h26" /></>),
  warn: (<><path d="M24 9 41 38H7z" /><path d="M24 19v9" /><path d="M24 33v.5" /></>),
  sliders: (<><path d="M9 15h13M30 15h9" /><circle cx="26" cy="15" r="4" /><path d="M9 33h7M24 33h15" /><circle cx="20" cy="33" r="4" /></>),
  close: (<><path d="M14 14l20 20" /><path d="M34 14 14 34" /></>),
  'theme-system': (<><rect x="8" y="10" width="32" height="22" rx="3" /><path d="M24 32v7" /><path d="M16 39h16" /></>),
  'theme-light': (<><circle cx="24" cy="24" r="7" /><path d="M24 8v4M24 36v4M8 24h4M36 24h4M12.7 12.7l2.8 2.8M32.5 32.5l2.8 2.8M12.7 35.3l2.8-2.8M32.5 15.5l2.8-2.8" /></>),
  'theme-dark': <path d="M38 27.5A15 15 0 1 1 20.5 10a11.5 11.5 0 0 0 17.5 17.5z" />,
  link: (<><path d="M20 14h-6a4 4 0 0 0-4 4v16a4 4 0 0 0 4 4h16a4 4 0 0 0 4-4v-6" /><path d="M26 10h12v12" /><path d="M38 10 22 26" /></>),
};

export function Ico({ name, size = 20, className }: { name: keyof typeof P; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 48 48" fill="none" stroke="currentColor"
      strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{P[name]}</svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth={3.2}
      strokeLinecap="round" strokeLinejoin="round" aria-label={PRODUCT.en}>
      <path d="M25 34 V11.5 a4.5 4.5 0 0 1 9 0 V30" /><path d="M34 30 v-1.5 a4.5 4.5 0 0 1 9 0 v3" />
      <path d="M43 31.5 a4.5 4.5 0 0 1 9 0 v6" />
      <path d="M52 37.5 v5.5 c0 7.5 -5 13 -12 13 h-9 c-7 0 -15 -6 -15 -15 v-2.5 c0 -3.5 3 -5.5 6.5 -4.5" />
      <path d="M25 34 c3 0.5 6 2 7.5 4.5 c1.5 2.5 3.5 3 6 3" />
    </svg>
  );
}
