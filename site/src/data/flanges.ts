// Robot flange patterns, kept apart from the arms that use them: an arm points at one entry (and may override its
// title, source or notes), and the "Custom flange" carrier offers them as starting points.
//   spec  what the info panel draws and lists (the robot side of the interface)
//   sets  the pusher base parameters that match it when the pusher is bolted on directly (adapter "None"):
//         clearance holes and counterbores in the printed base, cut in the robot flange frame F_robot
// With a flange adapter between robot and pusher, the adapter decides these parameters instead (catalog.ts).
// The pusher base has 4 screw holes for now: two pairs of opposite holes, hole_ang2 apart (90 = a square
// pattern, anything else = a rectangle). ISO 9409-1-80-6-M8 of UR20/UR30 needs a 6-hole base first.
import type { Txt } from '../i18n';

export interface FlangeSpec {
  title: Txt;                 // e.g. "ISO 9409-1-50-4-M6"
  pcd: number;                // pitch circle diameter of the screw holes, mm
  holes: number;
  thread: string;             // e.g. "M6"
  threadDepth: Txt;
  threadDepthVerify?: boolean;
  firstHoleDeg: number;       // angle of the first hole from +X of the flange frame
  holeAngles?: number[];      // all hole angles, when they are not evenly spaced (a rectangular pattern)
  outerD?: number;            // flange outer diameter (drawing only)
  pilot?: { d: number; fit?: string; depth?: string };   // centring recess
  pin?: { d: number; fit?: string; deg: number; pcd: number; depth?: string };
  screws: Txt;                // which screws, how many
  note?: Txt;
  source: Txt;
}

export interface FlangeStd {
  label: Txt;
  spec: FlangeSpec;
  sets: Record<string, number>;
}

/** Hole angles of a flange, in degrees from +X of the flange frame. */
export function holeAngles(spec: FlangeSpec): number[] {
  return spec.holeAngles ?? Array.from({ length: spec.holes }, (_, i) => spec.firstHoleDeg + (360 / spec.holes) * i);
}

export const FLANGES = {
  iso50: {
    label: 'ISO 9409-1-50-4-M6',
    sets: {
      base_R: 31.5, hole_pcd: 50, hole_d: 6.6, hole_rot: 45, hole_ang2: 90, cbore_d: 11, cbore_depth: 6.5,
      relief_h: 0, screw_head_d: 10, screw_head_h: 6,
    },
    spec: {
      title: 'ISO 9409-1-50-4-M6', pcd: 50, holes: 4, thread: 'M6', firstHoleDeg: 45, outerD: 63,
      threadDepth: { en: 'to verify (see the official flange drawing)', zh: '待核实（见官方法兰图）' }, threadDepthVerify: true,
      pilot: { d: 31.5, fit: 'H7' },
      pin: { d: 6, fit: 'H7', deg: 0, pcd: 50 },
      screws: { en: '4 × M6 socket head cap screws (class 8.8) + 1 × Ø6 dowel pin', zh: '4 × M6 内六角圆柱头螺钉（8.8 级）+ 1 个 Ø6 定位销' },
      note: {
        en: 'Hole pattern per ISO 9409-1-A50; angular positions per the official drawing.',
        zh: '孔位为 ISO 9409-1-A50 标准图样；角度位置以官方图纸为准。',
      },
      source: 'ISO 9409-1:2004',
    },
  },
  rebot: {
    label: { en: 'reBot B601-RS joint-6 rotor (4 × M3, Ø27)', zh: 'reBot B601-RS 第 6 关节转子（4 × M3，Ø27）' },
    sets: {
      base_R: 28.4, hole_pcd: 27, hole_d: 3.4, hole_rot: 30, hole_ang2: 120, cbore_d: 6.5, cbore_depth: 7,
      relief_h: 2, screw_head_d: 5.5, screw_head_h: 3,
    },
    spec: {
      title: { en: 'reBot B601-RS end flange (joint-6 rotor face)', zh: 'reBot B601-RS 末端法兰（第 6 关节转子端面）' },
      pcd: 27, holes: 4, thread: 'M3', firstHoleDeg: 30, holeAngles: [30, 150, 210, 330], outerD: 35.6,
      threadDepth: { en: 'to measure', zh: '待实测' }, threadDepthVerify: true,
      screws: {
        en: '4 × M3 socket head cap screws (the official gripper connector uses the same four)',
        zh: '4 × M3 内六角圆柱头螺钉（官方夹爪连接件也是用这 4 个）',
      },
      note: {
        en: 'The real flange is small: 4 × M3 on a 23.4 × 13.5 mm rectangle (Ø27 circle, at 30°/150°/210°/330° in the URDF link6 frame). Three Ø4 pins at R 12.15 and the centre boss stand proud of the face, so a part bolted on directly needs a 2 mm relief.',
        zh: '真实法兰很小：4 × M3 排成 23.4 × 13.5 mm 的矩形（节圆 Ø27，在 URDF link6 坐标系里位于 30°/150°/210°/330°）。端面上有 3 个 R 12.15 的 Ø4 销和中心凸台，直接装上去的零件要留 2 mm 让位。',
      },
      source: {
        en: 'Official STEP of the gripper connector (reBot-DevArm, Metal_Parts/2-M6-ROTOR.step), checked against the URDF link6 mesh',
        zh: '官方夹爪连接件 STEP（reBot-DevArm，Metal_Parts/2-M6-ROTOR.step），并与 URDF 的 link6 网格核对',
      },
    },
  },
} satisfies Record<string, FlangeStd>;

export type FlangeId = keyof typeof FLANGES;

/** The parameters a custom flange is made of (editable when the carrier is "Custom flange"). */
export const FLANGE_PARAMS = ['base_R', 'hole_pcd', 'hole_d', 'hole_rot', 'hole_ang2', 'cbore_d', 'cbore_depth', 'relief_h', 'screw_head_d', 'screw_head_h'] as const;

/** The four hole angles of the pusher base, in the robot flange frame. */
export function baseHoleAngles(P: Record<string, number>): number[] {
  const a = P.hole_rot, b = P.hole_ang2 ?? 90;
  return [a, a + b, a + 180, a + 180 + b];
}

/** Drawing data for the hole pattern of the pusher base as it is now (follows the adapter, or the carrier when
 *  there is no adapter). Null when the base has no screws (mount_screws = 0: the connector cup is printed in). */
export function basePatternSpec(P: Record<string, number>): FlangeSpec | null {
  if (!P.mount_screws) return null;
  const through = P.mount_screws === 2;
  const d = +P.hole_d.toFixed(2);
  return {
    title: { en: 'Pusher base holes', zh: '推杆底座孔位' },
    pcd: P.hole_pcd, holes: 4, thread: `Ø${d}`, firstHoleDeg: P.hole_rot, outerD: 2 * P.base_R, holeAngles: baseHoleAngles(P),
    threadDepth: '',
    screws: through
      ? { en: `4 screws from the tool side: Ø${d} through holes, counterbore Ø${+P.cbore_d.toFixed(2)} × ${+P.cbore_depth.toFixed(2)} deep`,
          zh: `4 个螺钉从工具一侧拧入：Ø${d} 通孔，沉孔 Ø${+P.cbore_d.toFixed(2)} 深 ${+P.cbore_depth.toFixed(2)}` }
      : { en: `4 screws from the adapter side into Ø${d} blind holes, ${+P.hole_depth.toFixed(1)} deep (self-tapping in the print)`,
          zh: `4 个螺钉从转接件一侧拧入 Ø${d} 盲孔，深 ${+P.hole_depth.toFixed(1)}（在打印件里自攻）` },
    source: '',
  };
}

/** Drawing data for a custom flange, from the current pusher parameters. */
export function customFlangeSpec(P: Record<string, number>): FlangeSpec {
  return {
    title: { en: 'Custom flange (from the base parameters)', zh: '自定义法兰（按底座参数）' },
    pcd: P.hole_pcd, holes: 4, thread: `Ø${+P.hole_d.toFixed(2)}`, firstHoleDeg: P.hole_rot, outerD: 2 * P.base_R,
    holeAngles: baseHoleAngles(P),
    threadDepth: { en: 'depends on your robot', zh: '取决于你的机械臂' },
    screws: {
      en: `4 screws through Ø${+P.hole_d.toFixed(2)} holes, counterbore Ø${+P.cbore_d.toFixed(2)} × ${+P.cbore_depth.toFixed(2)} deep`,
      zh: `4 个螺钉穿 Ø${+P.hole_d.toFixed(2)} 通孔，沉孔 Ø${+P.cbore_d.toFixed(2)} 深 ${+P.cbore_depth.toFixed(2)}`,
    },
    source: { en: 'Your values', zh: '你填的值' },
  };
}
