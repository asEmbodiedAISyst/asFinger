// The phones of the camera group. Geometry (body, lens and sensor positions, camera glass height) comes from
// iMuninn's phone data, which reads Apple's dimensional drawings (phones.json, written by
// scripts/phones-from-imuninn.mjs). Camera specifications are from Apple's tech-spec pages (SPECS below).
//
// Picking a phone fixes the phone parameters of the pusher config (`sets`) and switches the config options
// `telephoto` and `lidar`; the camera solve then places the phone so that its main camera looks at the TCP, and the
// holder follows (it sits on the phone's MagSafe circle). The iPhone 17 Pro values equal those in the config file.
import type { Txt } from '../i18n';
import type { CatalogItem, InfoRow } from './catalog';
import PHONES from './phones.json';

interface Spec {
  body: string;                 // Apple: height × width × depth, weight
  main: Txt; ultraWide: Txt; tele?: Txt; video: Txt;
  feq: number; feqTele?: number; lidar: boolean;
  support: string;              // Apple tech-spec page
  extra?: InfoRow[];            // rows shown after the body
  measured?: Txt;               // what was checked on a real phone
  holderMadeFor?: boolean;      // the holder and case gap were made for this phone
}

const SPECS: Record<string, Spec> = {
  iphone17pro: {
    body: '150.0 × 71.9 × 8.75 mm, 206 g',
    main: { en: '48 MP Fusion, 24 mm, ƒ/1.78, 2nd-gen sensor-shift OIS', zh: '48 MP Fusion，24 mm，ƒ/1.78，第二代传感器位移防抖' },
    ultraWide: { en: '48 MP, 13 mm, ƒ/2.2, 120° FOV', zh: '48 MP，13 mm，ƒ/2.2，120° 视场' },
    tele: '48 MP, 100 mm (4×), ƒ/2.8',
    video: { en: '4K 120 fps (main), 1080p slo-mo 240 fps', zh: '4K 120 fps（主摄），1080p 慢动作 240 fps' },
    feq: 24, feqTele: 100, lidar: true, support: 'https://support.apple.com/125090',
    extra: [
      { label: { en: 'Sensor size', zh: '传感器尺寸' }, value: { en: 'not published by Apple', zh: '官方未公布' }, verify: true },
      { label: { en: 'Min focus distance', zh: '最近对焦距离' }, value: { en: 'not published, to measure', zh: '官方未公布，需实测' }, verify: true },
    ],
    measured: { en: 'Camera glass height checked with calipers on a real phone (2026-11-27)', zh: '镜头玻璃高度已用卡尺在真机上核对（2026-11-27）' },
    holderMadeFor: true,
  },
  iphone18pro: {
    body: '150.0 × 71.9 × 8.75 mm, 211 g',
    main: { en: '48 MP Fusion, 24 mm, variable aperture ƒ/1.48 to ƒ/4.0', zh: '48 MP Fusion，24 mm，可变光圈 ƒ/1.48 到 ƒ/4.0' },
    ultraWide: { en: '48 MP Fusion, 13 mm, ƒ/2.2, 120° FOV', zh: '48 MP Fusion，13 mm，ƒ/2.2，120° 视场' },
    tele: '48 MP Fusion, 100 mm (4×), ƒ/2.8',
    video: { en: '4K 120 fps (main)', zh: '4K 120 fps（主摄）' },
    feq: 24, feqTele: 100, lidar: true, support: 'https://support.apple.com/en-us/148590',
  },
  iphone17: {
    body: '149.6 × 71.5 × 7.95 mm, 177 g',
    main: { en: '48 MP Fusion, 26 mm, ƒ/1.6', zh: '48 MP Fusion，26 mm，ƒ/1.6' },
    ultraWide: { en: '48 MP Fusion, 13 mm, ƒ/2.2, 120° FOV', zh: '48 MP Fusion，13 mm，ƒ/2.2，120° 视场' },
    video: '4K 60 fps',
    feq: 26, lidar: false, support: 'https://support.apple.com/en-us/125089',
  },
  iphone16pro: {
    body: '149.6 × 71.5 × 8.25 mm, 199 g',
    main: { en: '48 MP Fusion, 24 mm, ƒ/1.78', zh: '48 MP Fusion，24 mm，ƒ/1.78' },
    ultraWide: { en: '48 MP, 13 mm, ƒ/2.2, 120° FOV', zh: '48 MP，13 mm，ƒ/2.2，120° 视场' },
    tele: { en: '12 MP, 120 mm (5×), ƒ/2.8, 20° FOV', zh: '12 MP，120 mm（5×），ƒ/2.8，20° 视场' },
    video: { en: '4K 120 fps (Fusion camera)', zh: '4K 120 fps（Fusion 主摄）' },
    feq: 24, feqTele: 120, lidar: true, support: 'https://support.apple.com/en-us/121031',
  },
  iphone15pro: {
    body: '146.6 × 70.6 × 8.25 mm, 187 g',
    main: { en: '48 MP, 24 mm, ƒ/1.78', zh: '48 MP，24 mm，ƒ/1.78' },
    ultraWide: { en: '12 MP, 13 mm, ƒ/2.2, 120° FOV', zh: '12 MP，13 mm，ƒ/2.2，120° 视场' },
    tele: '12 MP, 77 mm (3×), ƒ/2.8',
    video: '4K 60 fps',
    feq: 24, feqTele: 77, lidar: true, support: 'https://support.apple.com/en-us/111829',
  },
  iphone14pro: {
    body: '147.5 × 71.5 × 7.85 mm, 206 g',
    main: { en: '48 MP, 24 mm, ƒ/1.78', zh: '48 MP，24 mm，ƒ/1.78' },
    ultraWide: { en: '12 MP, 13 mm, ƒ/2.2, 120° FOV', zh: '12 MP，13 mm，ƒ/2.2，120° 视场' },
    tele: '12 MP, 77 mm (3×), ƒ/2.8',
    video: '4K 60 fps',
    feq: 24, feqTele: 77, lidar: true, support: 'https://support.apple.com/en-us/111849',
  },
};

type Phone = (typeof PHONES.phones)[number];
const phone = (id: string): Phone => {
  const p = PHONES.phones.find((q) => q.id === id);
  if (!p) throw new Error(`phones.json has no ${id}`);
  return p;
};
const mm = (v: number) => `${v.toFixed(2)} mm`;

const IMUNINN_PAGE = 'https://imuninn.projects.weijinqi.com/en/parameter-definition/';

function drawingRows(p: Phone): InfoRow[] {
  const s = p.sets as Record<string, number>;
  return [
    {
      label: { en: 'Main lens in the model', zh: '模型里的主摄' },
      value: {
        en: `x ${mm(s.lens_x)}, y ${mm(s.lens_y)} from the display centre; glass ${mm(s.bump_h)} above the back (camera plateau ${mm(p.camera_plateau ?? 0)})`,
        zh: `距屏幕中心 x ${mm(s.lens_x)}、y ${mm(s.lens_y)}；镜头玻璃高出背面 ${mm(s.bump_h)}（镜头平台 ${mm(p.camera_plateau ?? 0)}）`,
      },
    },
    {
      label: { en: 'Dimensions source', zh: '尺寸来源' },
      value: {
        en: `Apple dimensional drawing (${p.drawing.date}), read into iMuninn's phone data by a program; not yet checked by a person`,
        zh: `Apple 尺寸图（${p.drawing.date}），由程序读进 iMuninn 的手机数据；还没有人工核对`,
      },
      verify: p.review !== 'human',
    },
  ];
}

const HOLDER_ROW: InfoRow = {
  label: { en: 'Holder', zh: '支架' },
  value: {
    en: "The slide-lock holder and the case gap (back_to_mount 3.25 mm) were made for an iPhone 17 Pro in its case. The model puts the holder on this phone's MagSafe circle; check the case thickness before printing.",
    zh: '滑锁支架和壳厚（back_to_mount 3.25 mm）是按带壳的 iPhone 17 Pro 做的。模型把支架放在这台手机的 MagSafe 圆心上；打印前要核对壳厚。',
  },
  verify: true,
};

function phoneItem(id: string): CatalogItem {
  const p = phone(id), s = SPECS[id];
  const sets: Record<string, number> = { ...(p.sets as Record<string, number>), feq: s.feq };
  if (s.feqTele) sets.feq_tele = s.feqTele;
  const lidarRow: Txt = !s.lidar ? { en: 'none', zh: '无' }
    : p.options.lidar ? { en: 'yes', zh: '有' }
    : { en: 'yes; its position is missing from the drawing data, so the model leaves the LiDAR frame out', zh: '有；尺寸图数据里缺它的位置，模型里先不放 LiDAR 坐标系' };
  return {
    id, name: p.name, subtitle: { en: 'Apple · landscape', zh: 'Apple · 横屏' }, icon: 'phone',
    sets, options: { telephoto: !!s.tele && p.options.telephoto, lidar: s.lidar && p.options.lidar },
    info: [
      { label: { en: 'Brand', zh: '品牌' }, value: 'Apple' },
      { label: { en: 'Main', zh: '主摄' }, value: s.main },
      { label: { en: 'Ultra Wide', zh: '超广角' }, value: s.ultraWide },
      { label: { en: 'Telephoto', zh: '长焦' }, value: s.tele ?? { en: 'none (2× is a crop of the main camera)', zh: '无（2× 是主摄裁切）' } },
      { label: { en: 'Max frame rate', zh: '最高帧率' }, value: s.video },
      { label: 'LiDAR', value: lidarRow, verify: s.lidar && !p.options.lidar },
      { label: { en: 'Body', zh: '机身' }, value: s.body },
      ...(s.extra ?? []),
      ...drawingRows(p),
      ...(s.measured ? [{ label: { en: 'Checked', zh: '已核对' }, value: s.measured }] : []),
      ...(s.holderMadeFor ? [] : [HOLDER_ROW]),
    ],
    links: [
      { label: { en: 'Apple tech specs', zh: 'Apple 官方技术规格' }, url: s.support },
      { label: { en: 'Apple dimensional drawing (PDF)', zh: 'Apple 尺寸图（PDF）' }, url: p.drawing.url },
      { label: { en: 'iMuninn iPhone parameters (3D, all frames)', zh: 'iMuninn iPhone 参数页（3D，全部坐标系）' }, url: IMUNINN_PAGE },
    ],
  };
}

/** Newest first; the iPhone 17 Pro is the default. */
export const PHONE_ITEMS: CatalogItem[] = [
  phoneItem('iphone18pro'), phoneItem('iphone17pro'), phoneItem('iphone17'), phoneItem('iphone16pro'), phoneItem('iphone15pro'), phoneItem('iphone14pro'),
];
