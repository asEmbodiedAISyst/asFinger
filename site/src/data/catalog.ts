// What the editor offers, group by group. Add a group or an item here; the UI picks it up.
// Text is `Txt`: a plain string when it reads the same in English and Chinese, else {en, zh}.
// Values marked `verify: true` are not from an official drawing yet and are shown as "to verify".
import type { Txt } from '../i18n';
import { FLANGES, type FlangeSpec } from './flanges';
import { PHONE_ITEMS } from './phones';
export type { FlangeSpec } from './flanges';

export type View = 'carrier' | 'adapter' | 'pusher' | 'tip' | 'camera';
export type Icon = 'arm6' | 'arm7' | 'hand' | 'rod' | 'tip-ball' | 'tip-sensor' | 'tip-surface' | 'phone' | 'depthcam' | 'rod-arc' | 'flange' | 'adapter-none' | 'adapter-ab' | 'adapter-fused' | 'humanoid' | 'camera-none' | 'rod-square' | 'rod-pad' | 'adapter-wrist';

/** A joint drawn away from the baked pose: `deg` on the joint turns the flange frame by `flangeDeg` about its Z. */
export interface JointTurn { name: string; deg: number; flangeDeg: number }

export interface InfoRow { label: Txt; value: Txt; verify?: boolean }
export interface Link { label: Txt; url: string }


export interface CatalogItem {
  id: string;
  name: Txt;
  subtitle?: Txt;
  icon: Icon;
  disabled?: boolean;         // shown as "planned"
  /** the cards of a group are shown in sections, with a divider between them; items of one section stay together */
  section?: number;
  info?: InfoRow[];
  links?: Link[];
  flange?: FlangeSpec;
  /** carrier: no carrier, the flange pattern of the pusher base is edited by hand (see flanges.ts) */
  customFlange?: boolean;
  /** pusher parameters this choice fixes.
   *  carrier: the hole pattern of the pusher base when it is bolted on directly (adapter "None").
   *  adapter: what the adapter decides (its height, which way the screws go, the hole pattern on its tool side).
   *  camera: the phone size and where its cameras are (see phones.ts). */
  sets?: Record<string, number>;
  /** carrier: default mount_rot (deg), the angle of the pusher about the flange axis, measured from +X of the robot
   *  flange frame to +X of the pusher (the side the rod leans to). Chosen per arm so that every arm in its display
   *  pose carries the pusher the same way: phone on top. The user can change it in the pusher parameters. */
  mountRot?: number;
  /** carrier: defaults that differ when the pusher is bolted on directly (adapter "None"), e.g. another mount_rot
   *  because the screws must stay reachable. `joint` = the last joint is drawn turned by this much, so the
   *  assembly still looks the same. pusher: the same, applied after the carrier's (a pusher whose beam already
   *  leaves the screws free keeps it where it is). */
  direct?: { defaults: Record<string, number>; joint?: JointTurn };
  /** carrier: the adapter picked when this carrier is selected */
  defaultAdapter?: string;
  /** adapter: value of the config option `adapter` (false = no adapter parts, pusher base on the robot flange) */
  option?: boolean;
  /** camera, adapter, tip: config options this choice switches (e.g. `telephoto: false` for a phone without one) */
  options?: Record<string, boolean>;
  /** adapter: carriers it fits (ids); tip: pushers it fits (ids); missing = all */
  fits?: string[];
  /** a switch shown under the selected card, e.g. the sensor of a tip. Each choice adds its own options and sets;
   *  the editor keeps the choice in the selection under `<group>.<key>`. */
  variant?: { key: string; label: Txt; default: string; choices: Variant[] };
  /** carrier: drawing data for the fallback model (used when no baked GLB exists, see src/data/arms.json) */
  arm?: { reach: number; dof: number };
  /** pusher: the asfinger config it is built from (a path under hardware/, as the site serves it) */
  config?: string;
}

export interface Variant { id: string; name: Txt; options?: Record<string, boolean>; sets?: Record<string, number> }

export interface Group {
  id: string;
  title: Txt;
  view: View;
  hint: Txt;
  items: CatalogItem[];
}

export const GROUPS: Group[] = [
  {
    id: 'carrier', title: { en: 'Carrier', zh: '载体' }, view: 'carrier',
    hint: { en: 'What the pusher is mounted on: a robot arm or a hand. Sets the robot flange pattern and the default mounting angle.', zh: '推杆装在谁身上：机械臂或人手。决定机械臂法兰孔位和默认安装转角。' },
    items: [
      {
        section: 0, id: 'hand', name: { en: 'Human hand', zh: '人手' }, subtitle: { en: 'Handheld grip · demos / data', zh: '手持握把 · 示教 / 采集' }, icon: 'hand',
        sets: FLANGES.rebot.sets, mountRot: 180, defaultAdapter: 'gripper_ab', direct: { defaults: { mount_rot: 90, beam_x: 18 } },
        flange: { ...FLANGES.rebot.spec, title: { en: 'Handheld grip interface (same holes as the reBot flange)', zh: '手持握把接口（沿用 reBot 法兰孔位）' } },
        info: [
          { label: { en: 'Use', zh: '用途' }, value: { en: 'Hold the same pusher by hand for teleoperation demos and data collection', zh: '手持同一根推杆做遥操作示教和数据采集' } },
          { label: { en: 'Interface', zh: '接口' }, value: { en: 'Same face as the reBot flange, so the same adapter and pusher fit both', zh: '端面与 reBot 法兰相同，同一套转接件和推杆两边通用' } },
          { label: { en: 'Grip model', zh: '握把模型' }, value: { en: 'placeholder, dimensions pending', zh: '示意，尺寸待补' }, verify: true },
        ],
      },
      {
        section: 0, id: 'custom', name: { en: 'Custom flange', zh: '自定义法兰' }, icon: 'flange', customFlange: true, defaultAdapter: 'none', mountRot: 180,
        direct: { defaults: FLANGES.iso50.sets },   // a starting point; every value stays editable
        subtitle: { en: 'No carrier · enter your own hole pattern', zh: '无载体 · 自己填孔位' },
        info: [
          { label: { en: 'Use', zh: '用途' }, value: { en: 'A robot or fixture that is not in the list. The hole pattern of the pusher base becomes editable in the pusher parameters; start from a standard there.', zh: '列表里没有的机械臂或夹具。推杆参数里的底座孔位变成可编辑，可以从某个标准开始改。' } },
          { label: { en: 'Limits', zh: '限制' }, value: { en: '4 screw holes on one circle, as two opposite pairs (square or rectangle)', zh: '一圈 4 个螺钉孔，两两相对（正方形或矩形）' } },
        ],
      },
      {
        section: 1, id: 'rebot_rs', name: 'reBot Arm RS', subtitle: { en: 'Seeed · 6-axis', zh: 'Seeed · 6 轴' }, icon: 'arm6', arm: { reach: 650, dof: 6 },
        sets: FLANGES.rebot.sets, flange: FLANGES.rebot.spec, mountRot: 180, defaultAdapter: 'gripper_ab',
        direct: { defaults: { mount_rot: 90, beam_x: 18 }, joint: { name: 'joint6', deg: -90, flangeDeg: 90 } },   // the joint-6 axis is −Z of link6
        info: [
          { label: { en: 'End flange', zh: '末端法兰' }, value: { en: 'The joint-6 rotor face (URDF link6 origin). The official gripper sits on a two-part connector on top of it; see the Flange adapter group.', zh: '第 6 关节的转子端面（URDF link6 原点）。官方夹爪是通过上面的两件式连接件装上去的，见“法兰转接件”一组。' } },
          { label: { en: 'DOF', zh: '自由度' }, value: { en: '6 (plus gripper)', zh: '6（另有夹爪）' } },
          { label: { en: 'Payload', zh: '负载' }, value: { en: 'about 1.5 kg', zh: '约 1.5 kg' } },
          { label: { en: 'Reach', zh: '臂展' }, value: { en: '650 mm (767 mm in later versions)', zh: '650 mm（后续版本 767 mm）' } },
          { label: { en: 'Repeatability', zh: '重复定位精度' }, value: '< 0.2 mm' },
          { label: { en: 'Motors', zh: '电机' }, value: { en: 'RobStride brushless joint motors', zh: 'RobStride 无刷关节电机' } },
          { label: { en: 'Model source', zh: '模型来源' }, value: { en: 'Seeed reBot B601-RS URDF meshes; meshes and design files are CERN-OHL-W-2.0', zh: 'Seeed reBot B601-RS URDF 网格；网格和设计文件均为 CERN-OHL-W-2.0' } },
        ],
        links: [
          { label: { en: 'reBot-DevArm (GitHub, design files)', zh: 'reBot-DevArm（GitHub，设计文件）' }, url: 'https://github.com/Seeed-Projects/reBot-DevArm' },
          { label: { en: 'Launch article (Hackster)', zh: 'Hackster 发布介绍' }, url: 'https://www.hackster.io/news/seeed-studio-officially-launches-the-rebot-arm-b601-releases-design-files-for-diy-robot-builders-8f491ddca483' },
        ],
      },
      {
        section: 1, id: 'franka_fr3', name: 'Franka FR3', subtitle: { en: 'Franka Robotics · 7-axis', zh: 'Franka Robotics · 7 轴' }, icon: 'arm7', arm: { reach: 855, dof: 7 },
        sets: FLANGES.iso50.sets, mountRot: 180, defaultAdapter: 'none',
        flange: {
          ...FLANGES.iso50.spec, title: 'DIN ISO 9409-1-A50',
          source: { en: 'Franka Research 3 datasheet (R02212 2.6); hole pattern per ISO 9409-1-A50', zh: 'Franka Research 3 数据表（R02212 2.6）；孔位按 ISO 9409-1-A50' },
          note: {
            en: 'Hole pattern per ISO 9409-1-A50. The Franka Production 3 manual shows two Ø6 H7 pin holes; whether FR3 has two as well is to verify.',
            zh: '孔位为 ISO 9409-1-A50 标准图样。Franka Production 3 手册写的是两个 Ø6 H7 销孔，FR3 是否同样是两个待核实。',
          },
        },
        info: [
          { label: { en: 'DOF', zh: '自由度' }, value: '7' },
          { label: { en: 'Rated payload', zh: '额定负载' }, value: '3 kg' },
          { label: { en: 'Reach', zh: '臂展' }, value: { en: '855 mm (flange)', zh: '855 mm（法兰）' } },
          { label: { en: 'Repeatability', zh: '重复定位精度' }, value: '< ±0.1 mm (ISO 9283)' },
          { label: { en: 'Arm weight', zh: '本体重量' }, value: { en: 'about 18.3 kg', zh: '约 18.3 kg' } },
          { label: { en: 'Model source', zh: '模型来源' }, value: { en: 'MuJoCo Menagerie franka_fr3, from Franka franka_description (Apache-2.0)', zh: 'MuJoCo Menagerie franka_fr3，源自 Franka 官方 franka_description（Apache-2.0）' } },
        ],
        links: [
          { label: { en: 'FR3 datasheet (PDF)', zh: 'FR3 数据表（PDF）' }, url: 'https://franka.de/hubfs/Datasheet%20Franka%20Research%203_R02212_2.6_EN_July%202026.pdf?hsLang=en' },
          { label: { en: 'Franka models and simulation', zh: 'Franka 官方模型与仿真' }, url: 'https://franka.de/models-and-simulation' },
          { label: 'MuJoCo Menagerie · franka_fr3', url: 'https://github.com/google-deepmind/mujoco_menagerie/tree/main/franka_fr3' },
        ],
      },
      {
        section: 1, id: 'ur5e', name: 'UR5e', subtitle: { en: 'Universal Robots · 6-axis', zh: 'Universal Robots · 6 轴' }, icon: 'arm6', arm: { reach: 850, dof: 6 },
        sets: FLANGES.iso50.sets, mountRot: 90, defaultAdapter: 'none',
        flange: {
          ...FLANGES.iso50.spec, title: 'EN ISO 9409-1-50-4-M6',
          source: { en: 'UR5e datasheet and user manual, "Mounting"', zh: 'UR5e 数据表与用户手册“安装说明”' },
          screws: { en: '4 × M6 socket head cap screws (class 8.8, 8 N·m) + 1 × Ø6 dowel pin', zh: '4 × M6 内六角圆柱头螺钉（8.8 级，拧紧力矩 8 N·m）+ 1 个 Ø6 定位销' },
        },
        info: [
          { label: { en: 'DOF', zh: '自由度' }, value: '6' },
          { label: { en: 'Payload', zh: '负载' }, value: '5 kg' },
          { label: { en: 'Reach', zh: '臂展' }, value: '850 mm' },
          { label: { en: 'Repeatability', zh: '重复定位精度' }, value: '±0.03 mm (ISO 9283)' },
          { label: { en: 'Weight', zh: '重量' }, value: { en: '20.7 kg (incl. cable)', zh: '20.7 kg（含线缆）' } },
          { label: { en: 'Model source', zh: '模型来源' }, value: { en: 'MuJoCo Menagerie universal_robots_ur5e, from the Universal Robots ROS description (BSD-3-Clause)', zh: 'MuJoCo Menagerie universal_robots_ur5e，源自 Universal Robots ROS 描述文件（BSD-3-Clause）' } },
        ],
        links: [
          { label: { en: 'UR5e datasheet', zh: 'UR5e 技术规格' }, url: 'https://www.universal-robots.com/manuals/latest/en/datasheets/ur5e/' },
          { label: { en: 'UR5e mounting (tool flange)', zh: 'UR5e 安装说明（工具法兰）' }, url: 'https://www.universal-robots.com/manuals/EN/HTML/SW10_9/Content/prod-usr-man/complianceUR5e/H_g5_sections/mechanical_interface_g5/mounting_descrip.htm' },
          { label: 'MuJoCo Menagerie · UR5e', url: 'https://github.com/google-deepmind/mujoco_menagerie/tree/main/universal_robots_ur5e' },
        ],
      },
      {
        section: 2, id: 'unitree_g1', name: 'Unitree G1', subtitle: { en: 'Unitree · humanoid', zh: 'Unitree · 人形' }, icon: 'humanoid',
        sets: FLANGES.rebot.sets, mountRot: 180, defaultAdapter: 'g1_wrist',
        // like the reBot without an adapter: the beam moves aside so that the 4 x M3 into the adapter stay reachable
        direct: { defaults: { beam_x: 18 } },
        info: [
          { label: { en: 'End interface', zh: '末端接口' }, value: { en: 'The right wrist end (URDF: right_wrist_yaw_link, 41.5 mm out along X). There is no flange: the hand is held by a split clamp ring, so the pusher needs the G1 wrist adapter.', zh: '右手腕末端（URDF：right_wrist_yaw_link 沿 X 向外 41.5 mm）。这里没有法兰，手是靠一个开口夹环夹住的，所以推杆要用 G1 腕部转接件。' } },
          { label: { en: 'Arm DOF', zh: '手臂自由度' }, value: { en: '7 per arm (29-DoF version); the 23-DoF version has no wrist pitch and yaw', zh: '每条手臂 7 个（29 自由度版本）；23 自由度版本没有腕部俯仰和偏航' } },
          { label: { en: 'Arm payload', zh: '手臂负载' }, value: { en: 'about 2 kg (G1), about 3 kg (G1 EDU)', zh: '约 2 kg（G1），约 3 kg（G1 EDU）' } },
          { label: { en: 'Pose shown', zh: '显示的姿态' }, value: { en: 'Standing, right arm raised so that the wrist end faces 30° below horizontal, like the arms', zh: '站立，右臂抬起，让手腕末端朝向水平以下 30°，和机械臂一致' } },
          { label: { en: 'Model source', zh: '模型来源' }, value: { en: 'MuJoCo Menagerie unitree_g1, from Unitree unitree_ros g1_description (BSD-3-Clause); right rubber hand left out', zh: 'MuJoCo Menagerie unitree_g1，源自 Unitree unitree_ros 的 g1_description（BSD-3-Clause）；去掉了右手橡胶手' } },
        ],
        links: [
          { label: 'MuJoCo Menagerie · unitree_g1', url: 'https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_g1' },
          { label: { en: 'Unitree g1_description (URDF / MJCF)', zh: 'Unitree g1_description（URDF / MJCF）' }, url: 'https://github.com/unitreerobotics/unitree_ros/tree/master/robots/g1_description' },
        ],
      },
    ],
  },
  {
    id: 'adapter', title: { en: 'Mount adapter', zh: '安装转接件' }, view: 'adapter',
    hint: { en: 'What sits between the carrier (a robot flange or a wrist) and the pusher base. Sets the hole pattern of the pusher base.', zh: '载体（机械臂法兰或手腕）和推杆底座之间的那一层。决定推杆底座的孔位。' },
    items: [
      {
        section: 0, id: 'none', name: { en: 'None', zh: '无' }, subtitle: { en: 'Pusher base bolted straight onto the robot flange', zh: '推杆底座直接装在机械臂法兰上' }, icon: 'adapter-none',
        fits: ['hand', 'custom', 'rebot_rs', 'franka_fr3', 'ur5e'],   // not a wrist without a flange (G1)
        option: false, sets: { adapter_h: 0, mount_screws: 2 },
        info: [
          { label: { en: 'Interface', zh: '接口' }, value: { en: 'The pusher base takes the hole pattern of the selected carrier (through holes with counterbores, screws from the tool side into the robot flange).', zh: '推杆底座直接用所选载体的法兰孔位（通孔 + 沉孔，螺钉从工具一侧拧进机械臂法兰）。' } },
          { label: { en: 'Good for', zh: '适用' }, value: { en: 'ISO 9409-1-50 flanges (UR, Franka): the screws sit outside the rod and are easy to reach.', zh: 'ISO 9409-1-50 法兰（UR、Franka）：螺钉在杆的外侧，容易够到。' } },
          { label: { en: 'reBot', zh: 'reBot' }, value: { en: 'Possible, but tight: the 4 × M3 holes lie under the rod root. The defaults turn the pusher 90° on the flange and move the beam so that three screws take a straight driver and the fourth a short hex key.', zh: '可以，但很挤：4 × M3 孔就在杆根下面。默认把推杆在法兰上转 90° 并挪开横梁，这样 3 个螺钉能用直螺丝刀，第 4 个要用短内六角扳手。' } },
        ],
      },
      {
        // the pusher printed on 2026-11-08
        section: 1, id: 'gripper_ab', name: { en: 'Connector A + B', zh: '连接件 A + B' }, icon: 'adapter-ab', fits: ['rebot_rs', 'hand'],
        subtitle: { en: 'reBot gripper connector · both official parts, pusher screwed onto part B', zh: 'reBot 夹爪连接件 · 两个官方零件都用，推杆用螺钉装在零件 B 上' },
        option: true,
        sets: { mount_screws: 2, base_R: 28.4, hole_pcd: 38.01, hole_rot: 45, hole_ang2: 90, hole_d: 3.2, cbore_d: 7.5, cbore_depth: 3.5, relief_h: 0, screw_head_d: 5.5, screw_head_h: 3 },
        info: [
          { label: { en: 'Part A', zh: '零件 A' }, value: { en: 'Official aluminium disc Ø35.6 × 6 (2-M6-ROTOR), 4 × M3 onto the joint-6 rotor. Stays on the arm.', zh: '官方铝件，Ø35.6 × 6 的圆盘（2-M6-ROTOR），4 × M3 拧在第 6 关节转子上。一直留在机械臂上。' } },
          { label: { en: 'Part B', zh: '零件 B' }, value: { en: 'Official cup Ø56.8 × 9.5 (2-M7-STATOR). Stays on the tool.', zh: '官方杯形件，Ø56.8 × 9.5（2-M7-STATOR）。一直留在工具上。' } },
          { label: { en: 'A to B', zh: 'A 和 B 之间' }, value: { en: 'B slides over A; 3 × M3 set screws from the side (120° apart) press on A.', zh: 'B 套在 A 上，侧面 3 个 M3 顶丝（互成 120°）顶住 A。' } },
          { label: { en: 'B to pusher', zh: 'B 和推杆之间' }, value: { en: '4 × M3 on Ø38.01 at 45°, from the tool side: Ø3.2 through holes with Ø7.5 × 3.5 counterbores in the printed base; the screws hold the base on part B.', zh: '4 × M3，节圆 Ø38.01、45° 方向，从工具一侧拧：打印底座上是 Ø3.2 通孔加 Ø7.5 × 3.5 沉孔，螺钉穿过底座把它固定在零件 B 上。' } },
          { label: { en: 'Status', zh: '状态' }, value: { en: 'This is the pusher printed on 2026-11-08 and used on the real reBot.', zh: '这就是 2026-11-08 打印、在真机上用的那一版推杆。' } },
        ],
        links: [{ label: { en: 'reBot-DevArm metal parts (STEP)', zh: 'reBot-DevArm 金属件（STEP）' }, url: 'https://github.com/Seeed-Projects/reBot-DevArm/tree/main/hardware/reBot_B601_RS/Metal_Parts' }],
      },
      {
        section: 1, id: 'gripper_fused', name: { en: 'Fused connector', zh: '一体连接件' }, icon: 'adapter-fused', fits: ['rebot_rs', 'hand'],
        subtitle: { en: 'reBot gripper connector · part A + a copy of part B printed as one piece with the pusher', zh: 'reBot 夹爪连接件 · 零件 A + 推杆底部一体打印出零件 B 的形状' },
        option: true,
        sets: { mount_screws: 0, base_R: 28.4, hole_pcd: 38, hole_rot: 45, hole_ang2: 90, hole_d: 2.6, cbore_d: 6.5, cbore_depth: 3.5, relief_h: 0, screw_head_d: 5.5, screw_head_h: 3 },
        info: [
          { label: { en: 'Part A', zh: '零件 A' }, value: { en: 'Official aluminium disc Ø35.6 × 6 (2-M6-ROTOR), 4 × M3 onto the joint-6 rotor. Stays on the arm.', zh: '官方铝件，Ø35.6 × 6 的圆盘（2-M6-ROTOR），4 × M3 拧在第 6 关节转子上。一直留在机械臂上。' } },
          { label: { en: 'Part B', zh: '零件 B' }, value: { en: 'Not used as a separate part: its cup (Ø56.8 × 9.5, bore Ø36) is printed at the bottom of the pusher.', zh: '不单独使用：它的杯形（Ø56.8 × 9.5，内孔 Ø36）直接打印在推杆底部。' } },
          { label: { en: 'Fixing', zh: '固定方式' }, value: { en: 'The cup slides over part A; 3 × M3 set screws from the side (120° apart) press on A.', zh: '杯口套在零件 A 上，侧面 3 个 M3 顶丝（互成 120°）顶住 A。' } },
          { label: { en: 'Screws in the base', zh: '底座上的螺钉' }, value: { en: 'none', zh: '没有' } },
          { label: { en: 'Status', zh: '状态' }, value: { en: 'Not printed yet. The printed pusher is "Connector A + B".', zh: '还没有打印过。已经打印的那一版是“连接件 A + B”。' } },
        ],
        links: [{ label: { en: 'reBot-DevArm metal parts (STEP)', zh: 'reBot-DevArm 金属件（STEP）' }, url: 'https://github.com/Seeed-Projects/reBot-DevArm/tree/main/hardware/reBot_B601_RS/Metal_Parts' }],
      },
      {
        section: 2, id: 'g1_wrist', name: { en: 'G1 wrist adapter', zh: 'G1 腕部转接件' }, icon: 'adapter-wrist', fits: ['unitree_g1'],
        subtitle: { en: 'Clamped in the Unitree G1 wrist · reBot hole pattern on the tool side', zh: '夹在 Unitree G1 手腕里 · 工具一侧是 reBot 孔位' },
        option: false, options: { g1_adapter: true },
        // the reBot rectangle turned 90 deg (long side along Y of the wrist frame): holes at 60/120/240/300 deg
        sets: { ...FLANGES.rebot.sets, adapter_h: 16, mount_screws: 2, hole_rot: 60, hole_ang2: 60, relief_h: 0 },
        info: [
          { label: { en: 'Wrist side', zh: '手腕一侧' }, value: { en: 'A plug that the G1 wrist clamp ring holds (2 × M3)', zh: '一个让 G1 手腕夹环（2 × M3）夹住的插头' } },
          { label: { en: 'Tool side', zh: '工具一侧' }, value: { en: 'Ø63 × 16 flange: 4 × M3 heat-set inserts on the reBot rectangle (23.4 × 13.6), turned 90° so that the rod leans down with the phone on top at wrist zero; also 4 × M4 inserts on PCD 50 on the axes, with side nut slots', zh: 'Ø63 × 16 的法兰：4 个 M3 热熔螺母在 reBot 的矩形孔位上（23.4 × 13.6），转过 90°，这样手腕在零位时杆朝下、手机在上；另有 4 个 M4 热熔螺母，节圆 Ø50、在轴线上，带侧面螺母槽' } },
          { label: { en: 'Pusher', zh: '推杆' }, value: { en: 'Any pusher made for the bare reBot flange: its base is screwed onto the adapter from the tool side', zh: '直接装 reBot 法兰的推杆都能用：底座从工具一侧用螺钉固定在转接件上' } },
          { label: { en: 'Status', zh: '状态' }, value: { en: 'Variant rot90 of the adapter, not printed yet; the mesh is drawn as it is', zh: '转接件的 rot90 版本，还没有打印过；这里直接画它的网格' } },
        ],
      },
    ],
  },
  {
    id: 'pusher', title: { en: 'Pusher', zh: '推杆' }, view: 'pusher',
    hint: { en: 'The rod and the phone holder. Tune it on the right.', zh: '推杆本体和手机支架。参数在右侧调整。' },
    items: [
      {
        id: 'pad', name: { en: 'Pad', zh: '指腹推杆' }, subtitle: { en: 'Square bar with an arc finger pad · one piece', zh: '方杆 + 弧面指腹 · 一体打印' }, icon: 'rod-pad',
        config: 'configs/pad_finger.json',
        // its holder beam is tied to the bar root by a web between the screws: bolted on directly it stays on the axis
        direct: { defaults: { beam_x: 0 } },
        info: [
          { label: { en: 'Rod', zh: '杆' }, value: { en: '22 × 22 square bar, 30° to the flange axis, with a 16 mm neck at the base', zh: '22 × 22 方杆，与法兰轴线成 30°，根部有 16 mm 宽的颈部' } },
          { label: { en: 'Fingertip', zh: '指尖' }, value: { en: 'Quarter cylinder R15 from the side face round to the flat end face: the finger pad. T_tcp is the middle of the arc (45°).', zh: '从侧面到平端面的 R15 四分之一圆柱，就是指腹。T_tcp 在圆弧中点（45°）。' } },
          { label: { en: 'Print', zh: '打印' }, value: { en: 'One piece with the standard tip. With the TPU tip the fingertip is a second body for a second material.', zh: '配标准末端时一体打印。配 TPU 指尖时指尖是第二个实体，用第二种材料打印。' } },
          { label: { en: 'Holder support', zh: '支架支撑' }, value: { en: 'Beam on the flange axis, 14 wide, tied to the bar root by a web that passes between two flange screws', zh: '横梁在法兰轴线上，宽 14，用一道腹板连到杆根，腹板从两颗法兰螺钉之间穿过' } },
          { label: 'TCP', value: { en: 'Where the round rod has its TCP, so the phone pose is the same', zh: '和圆杆推杆的 TCP 在同一位置，所以手机位姿不变' } },
          { label: { en: 'Origin', zh: '来源' }, value: { en: 'The tactile finger of 2026-11-24 without its sensor', zh: '2026-11-24 的触觉指尖去掉传感器' } },
        ],
      },
      {
        id: 'round', name: { en: 'Round', zh: '圆杆推杆' }, subtitle: { en: 'Ø15 round rod, reinforced support · printed and in use', zh: 'Ø15 圆杆，加强支撑 · 已打印、在用' }, icon: 'rod',
        config: 'configs/iphone17pro_default.json',
        info: [
          { label: { en: 'Process', zh: '加工方式' }, value: { en: 'FDM 3D printing (PLA / PETG)', zh: 'FDM 3D 打印（PLA / PETG）' } },
          { label: { en: 'Print orientation', zh: '打印方向' }, value: { en: 'Base face down; the phone plate and snaps need supports', zh: '底座安装面朝下；手机支撑板和卡扣需要支撑' } },
          { label: { en: 'Known issue', zh: '已知问题' }, value: { en: 'The snaps are brittle in PLA matte and break easily; print them flat as a separate part or use PETG', zh: '卡扣用 PLA matte 打印很脆，易断；建议卡扣单独平放打印或改用 PETG' } },
        ],
      },
      {
        id: 'square', name: { en: 'Square', zh: '方杆推杆' }, subtitle: { en: '10 × 10 square rod, flat end · the earlier shape', zh: '10 × 10 方杆，平头 · 更早的形状' }, icon: 'rod-square',
        config: 'configs/square_rod.json',
        info: [
          { label: { en: 'Rod', zh: '杆' }, value: { en: '10 × 10 mm square, flat end; same place, angle (30°) and length as the round rod', zh: '10 × 10 mm 方杆，平头；位置、角度（30°）和长度都和圆杆相同' } },
          { label: 'TCP', value: { en: 'Centre of the flat end face (T_tcp = T_tip)', zh: '平头端面中心（T_tcp = T_tip）' } },
          { label: { en: 'Source', zh: '来源' }, value: { en: 'Measured on the first printed tool, modelled in Fusion (iPhone17_DataTool); the rod end agrees with that model to 0.02 mm', zh: '按最早打印的那一版测得，Fusion 模型 iPhone17_DataTool；杆端和该模型相差 0.02 mm' } },
          { label: { en: 'Holder', zh: '手机支架' }, value: { en: 'As on the Round pusher, without the back reinforcement (the first tool did not have it)', zh: '和圆杆推杆相同，但没有背部加强（最早那一版没有）' } },
        ],
      },
    ],
  },
  {
    id: 'tip', title: { en: 'Tip', zh: '末端' }, view: 'tip',
    hint: { en: 'The part that touches the object. The TCP is defined here.', zh: '和物体接触的部分。TCP 定义在这里。' },
    items: [
      {
        section: 0, id: 'bare', name: { en: 'Standard tip', zh: '标准末端' }, subtitle: { en: 'The pusher\'s own end, unchanged', zh: '推杆自带的末端，不做调整' }, icon: 'tip-ball',
        info: [
          { label: { en: 'Shape', zh: '形状' }, value: { en: 'Round: hemisphere, radius = rod diameter / 2. Square: the flat end face. Pad: the R15 finger pad.', zh: '圆杆：半球，半径 = 杆径 / 2。方杆：平端面。指腹：R15 的指腹圆弧。' } },
          { label: 'TCP', value: { en: 'Apex of the hemisphere, centre of the end face, middle of the pad arc (T_tcp)', zh: '半球顶点、端面中心、指腹圆弧中点（T_tcp）' } },
          { label: { en: 'Material', zh: '材料' }, value: { en: 'Same as the rod (printed)', zh: '与推杆相同（打印件）' } },
          { label: { en: 'Friction coefficient', zh: '摩擦系数' }, value: '—' },
          { label: { en: 'Sensor', zh: '传感器' }, value: { en: 'none', zh: '无' } },
        ],
      },
      {
        section: 1, id: 'soft_tpu', name: { en: 'Soft TPU tip', zh: 'TPU 软指尖' }, subtitle: { en: 'For the Pad pusher · optional 48 × 48 e-skin', zh: '配指腹推杆 · 可选 48 × 48 电子皮肤' }, icon: 'tip-sensor',
        fits: ['pad'], sets: { tip_split: 1 },
        variant: {
          key: 'sensor', label: { en: 'Sensor', zh: '传感器' }, default: 'eskin',
          choices: [
            { id: 'none', name: { en: 'None', zh: '无' }, options: { tactile: false } },
            { id: 'eskin', name: { en: '48 × 48 e-skin', zh: '48 × 48 电子皮肤' }, options: { tactile: true } },
          ],
        },
        info: [
          { label: { en: 'Shape', zh: '形状' }, value: { en: 'The last 29 mm of the Pad finger as its own body: the R15 pad and the flat end, meeting the bar on a flat face (14 mm straight part)', zh: '指腹推杆最末端 29 mm 单独成一个实体：R15 指腹和平端面，和杆在一个平面上相接（直段 14 mm）' } },
          { label: { en: 'Material', zh: '材料' }, value: 'TPU 95A' },
          { label: { en: 'Print', zh: '打印' }, value: { en: 'Load tool_body and tip_tpu as two parts of one object and give tip_tpu the TPU filament; the slicer joins them on the flat face', zh: '把 tool_body 和 tip_tpu 作为同一个对象的两个零件导入，tip_tpu 用 TPU 耗材；切片软件在平面上把两者接起来' } },
          { label: { en: 'Sensor', zh: '传感器' }, value: { en: 'Switch under the card. 48 × 48 e-skin: the pad (20 wide, 23.5 along the arc) sits in a 0.3 mm recess on the arc, its FPC runs in a groove under the bar to the readout PCB (STM32G474), which sits in a pocket near the base under a clip-on cover', zh: '在卡片下方切换。48 × 48 电子皮肤：皮肤（宽 20，沿圆弧 23.5）放在圆弧上 0.3 mm 深的凹槽里，FPC 沿杆下方的槽走到读出板（STM32G474），读出板放在底座附近的槽里，用卡扣盖板盖住' } },
          { label: 'TCP', value: { en: 'Middle of the pad arc, as with the standard tip', zh: '指腹圆弧中点，和标准末端相同' } },
          { label: { en: 'Status', zh: '状态' }, value: { en: 'Printed in TPU on 2026-11-26', zh: '2026-11-26 用 TPU 打印成功' } },
        ],
      },
    ],
  },
  {
    id: 'camera', title: { en: 'Camera', zh: '相机' }, view: 'camera',
    hint: { en: 'The phone or camera on the pusher. Sets the view.', zh: '装在推杆上的手机或相机，决定视野。' },
    items: [
      {
        section: 0, id: 'none', name: { en: 'None', zh: '无' }, subtitle: { en: 'The pusher alone, no camera', zh: '只有推杆，不带相机' }, icon: 'camera-none',
        options: { phone: false, telephoto: false, lidar: false },
        info: [
          { label: { en: 'Built', zh: '生成' }, value: { en: 'The rod and its base only: the phone, its holder, the beam and the spine are left out, and the camera solve is skipped.', zh: '只有推杆和底座：手机、手机支架、横梁和支撑条都去掉，也不做相机求解。' } },
        ],
      },
      ...PHONE_ITEMS.map((p) => ({ ...p, section: 1 })),
      { section: 2, id: 'realsense_d435i', name: 'RealSense D435i', subtitle: { en: 'Intel · depth camera · placeholder', zh: 'Intel · 深度相机 · 占位' }, icon: 'depthcam', disabled: true },
    ],
  },
];

export const DEFAULT_SELECTION: Record<string, string> = { carrier: 'rebot_rs', adapter: 'gripper_ab', pusher: 'round', tip: 'bare', camera: 'iphone17pro' };

export function item(groupId: string, id: string): CatalogItem | undefined {
  return GROUPS.find((g) => g.id === groupId)?.items.find((i) => i.id === id);
}

/** Whether an adapter can be used with a carrier, or a tip with a pusher. */
export function fits(it: CatalogItem | undefined, otherId: string): boolean {
  return !!it && !it.disabled && (!it.fits || it.fits.includes(otherId));
}

/** The variant choice of an item in a selection (its default when none is stored or the stored one is gone). */
export function variantOf(groupId: string, it: CatalogItem | undefined, selection: Record<string, string>): Variant | undefined {
  const v = it?.variant;
  if (!v) return undefined;
  return v.choices.find((c) => c.id === selection[`${groupId}.${v.key}`]) ?? v.choices.find((c) => c.id === v.default);
}
