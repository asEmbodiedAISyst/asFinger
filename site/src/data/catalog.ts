// What the editor offers, group by group. Add a group or an item here; the UI picks it up.
// Text is `Txt`: a plain string when it reads the same in English and Chinese, else {en, zh}.
// Values marked `verify: true` are not from an official drawing yet and are shown as "to verify".
import type { Txt } from '../i18n';
import { FLANGES, type FlangeSpec } from './flanges';
export type { FlangeSpec } from './flanges';

export type View = 'carrier' | 'adapter' | 'pusher' | 'tip' | 'camera';
export type Icon = 'arm6' | 'arm7' | 'hand' | 'rod' | 'tip-ball' | 'tip-sensor' | 'tip-surface' | 'phone' | 'depthcam' | 'rod-arc' | 'flange' | 'adapter-none' | 'adapter-ab' | 'adapter-fused';

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
  info?: InfoRow[];
  links?: Link[];
  flange?: FlangeSpec;
  /** carrier: no carrier, the flange pattern of the pusher base is edited by hand (see flanges.ts) */
  customFlange?: boolean;
  /** pusher parameters this choice fixes.
   *  carrier: the hole pattern of the pusher base when it is bolted on directly (adapter "None").
   *  adapter: what the adapter decides (its height, which way the screws go, the hole pattern on its tool side). */
  sets?: Record<string, number>;
  /** carrier: default mount_rot (deg), the angle of the pusher about the flange axis, measured from +X of the robot
   *  flange frame to +X of the pusher (the side the rod leans to). Chosen per arm so that every arm in its display
   *  pose carries the pusher the same way: phone on top. The user can change it in the pusher parameters. */
  mountRot?: number;
  /** carrier: defaults that differ when the pusher is bolted on directly (adapter "None"), e.g. another mount_rot
   *  because the screws must stay reachable. `joint` = the last joint is drawn turned by this much, so the
   *  assembly still looks the same. */
  direct?: { defaults: Record<string, number>; joint?: JointTurn };
  /** carrier: the adapter picked when this carrier is selected */
  defaultAdapter?: string;
  /** adapter: value of the config option `adapter` (false = no adapter parts, pusher base on the robot flange) */
  option?: boolean;
  /** adapter: carriers it fits (ids); missing = all */
  fits?: string[];
  /** carrier: drawing data for the fallback model (used when no baked GLB exists, see src/data/arms.json) */
  arm?: { reach: number; dof: number };
  /** pusher: the asfinger config it is built from (a path under hardware/, as the site serves it) */
  config?: string;
}

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
        id: 'custom', name: { en: 'Custom flange', zh: '自定义法兰' }, icon: 'flange', customFlange: true, defaultAdapter: 'none', mountRot: 180,
        direct: { defaults: FLANGES.iso50.sets },   // a starting point; every value stays editable
        subtitle: { en: 'No carrier · enter your own hole pattern', zh: '无载体 · 自己填孔位' },
        info: [
          { label: { en: 'Use', zh: '用途' }, value: { en: 'A robot or fixture that is not in the list. The hole pattern of the pusher base becomes editable in the pusher parameters; start from a standard there.', zh: '列表里没有的机械臂或夹具。推杆参数里的底座孔位变成可编辑，可以从某个标准开始改。' } },
          { label: { en: 'Limits', zh: '限制' }, value: { en: '4 screw holes on one circle, as two opposite pairs (square or rectangle)', zh: '一圈 4 个螺钉孔，两两相对（正方形或矩形）' } },
        ],
      },
      {
        id: 'rebot_rs', name: 'reBot Arm RS', subtitle: { en: 'Seeed · 6-axis', zh: 'Seeed · 6 轴' }, icon: 'arm6', arm: { reach: 650, dof: 6 },
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
        id: 'franka_fr3', name: 'Franka FR3', subtitle: { en: 'Franka Robotics · 7-axis', zh: 'Franka Robotics · 7 轴' }, icon: 'arm7', arm: { reach: 855, dof: 7 },
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
        id: 'ur5e', name: 'UR5e', subtitle: { en: 'Universal Robots · 6-axis', zh: 'Universal Robots · 6 轴' }, icon: 'arm6', arm: { reach: 850, dof: 6 },
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
        id: 'hand', name: { en: 'Human hand', zh: '人手' }, subtitle: { en: 'Handheld grip · demos / data', zh: '手持握把 · 示教 / 采集' }, icon: 'hand',
        sets: FLANGES.rebot.sets, mountRot: 180, defaultAdapter: 'gripper_ab', direct: { defaults: { mount_rot: 90, beam_x: 18 } },
        flange: { ...FLANGES.rebot.spec, title: { en: 'Handheld grip interface (same holes as the reBot flange)', zh: '手持握把接口（沿用 reBot 法兰孔位）' } },
        info: [
          { label: { en: 'Use', zh: '用途' }, value: { en: 'Hold the same pusher by hand for teleoperation demos and data collection', zh: '手持同一根推杆做遥操作示教和数据采集' } },
          { label: { en: 'Interface', zh: '接口' }, value: { en: 'Same face as the reBot flange, so the same adapter and pusher fit both', zh: '端面与 reBot 法兰相同，同一套转接件和推杆两边通用' } },
          { label: { en: 'Grip model', zh: '握把模型' }, value: { en: 'placeholder, dimensions pending', zh: '示意，尺寸待补' }, verify: true },
        ],
      },
    ],
  },
  {
    id: 'adapter', title: { en: 'Flange adapter', zh: '法兰转接件' }, view: 'adapter',
    hint: { en: 'What sits between the robot flange and the pusher base. Sets the hole pattern of the pusher base.', zh: '机械臂法兰和推杆底座之间的那一层。决定推杆底座的孔位。' },
    items: [
      {
        id: 'none', name: { en: 'None', zh: '无' }, subtitle: { en: 'Pusher base bolted straight onto the robot flange', zh: '推杆底座直接装在机械臂法兰上' }, icon: 'adapter-none',
        option: false, sets: { adapter_h: 0, mount_screws: 2 },
        info: [
          { label: { en: 'Interface', zh: '接口' }, value: { en: 'The pusher base takes the hole pattern of the selected carrier (through holes with counterbores, screws from the tool side into the robot flange).', zh: '推杆底座直接用所选载体的法兰孔位（通孔 + 沉孔，螺钉从工具一侧拧进机械臂法兰）。' } },
          { label: { en: 'Good for', zh: '适用' }, value: { en: 'ISO 9409-1-50 flanges (UR, Franka): the screws sit outside the rod and are easy to reach.', zh: 'ISO 9409-1-50 法兰（UR、Franka）：螺钉在杆的外侧，容易够到。' } },
          { label: { en: 'reBot', zh: 'reBot' }, value: { en: 'Possible, but tight: the 4 × M3 holes lie under the rod root. The defaults turn the pusher 90° on the flange and move the beam so that three screws take a straight driver and the fourth a short hex key.', zh: '可以，但很挤：4 × M3 孔就在杆根下面。默认把推杆在法兰上转 90° 并挪开横梁，这样 3 个螺钉能用直螺丝刀，第 4 个要用短内六角扳手。' } },
        ],
      },
      {
        // the pusher printed on 2026-11-08
        id: 'gripper_ab', name: { en: 'Connector A + B', zh: '连接件 A + B' }, icon: 'adapter-ab', fits: ['rebot_rs', 'hand'],
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
        id: 'gripper_fused', name: { en: 'Fused connector', zh: '一体连接件' }, icon: 'adapter-fused', fits: ['rebot_rs', 'hand'],
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
    ],
  },
  {
    id: 'pusher', title: { en: 'Pusher', zh: '推杆' }, view: 'pusher',
    hint: { en: 'The rod and the phone holder. Tune it on the right.', zh: '推杆本体和手机支架。参数在右侧调整。' },
    items: [
      {
        id: 'rod_v1', name: { en: 'Round rod v1', zh: '圆杆推杆 v1' }, subtitle: { en: 'Ø15 rod · printed and tested', zh: 'Ø15 圆杆 · 已打印验证' }, icon: 'rod',
        config: 'configs/iphone17pro_default.json',
        info: [
          { label: { en: 'Process', zh: '加工方式' }, value: { en: 'FDM 3D printing (PLA / PETG)', zh: 'FDM 3D 打印（PLA / PETG）' } },
          { label: { en: 'Print orientation', zh: '打印方向' }, value: { en: 'Base face down; the phone plate and snaps need supports', zh: '底座安装面朝下；手机支撑板和卡扣需要支撑' } },
          { label: { en: 'Known issue', zh: '已知问题' }, value: { en: 'The snaps are brittle in PLA matte and break easily; print them flat as a separate part or use PETG', zh: '卡扣用 PLA matte 打印很脆，易断；建议卡扣单独平放打印或改用 PETG' } },
        ],
      },
      { id: 'rod_arc', name: { en: 'Arc-pad pusher', zh: '弧面推杆' }, icon: 'rod-arc', disabled: true },
    ],
  },
  {
    id: 'tip', title: { en: 'Tip', zh: '末端' }, view: 'tip',
    hint: { en: 'The part that touches the object. The TCP is defined here.', zh: '和物体接触的部分。TCP 定义在这里。' },
    items: [
      {
        id: 'bare', name: { en: 'Bare tip', zh: '裸末端' }, subtitle: { en: 'Hemisphere · part of the rod', zh: '半球 · 与推杆一体' }, icon: 'tip-ball',
        info: [
          { label: { en: 'Shape', zh: '形状' }, value: { en: 'Hemisphere, radius = rod diameter / 2', zh: '半球，半径 = 杆径 / 2' } },
          { label: 'TCP', value: { en: 'Apex of the hemisphere (T_tcp)', zh: '半球顶点（T_tcp）' } },
          { label: { en: 'Material', zh: '材料' }, value: { en: 'Same as the rod (printed)', zh: '与推杆相同（打印件）' } },
          { label: { en: 'Friction coefficient', zh: '摩擦系数' }, value: '—' },
          { label: { en: 'Sensor', zh: '传感器' }, value: { en: 'none', zh: '无' } },
        ],
      },
      { id: 'surface', name: { en: 'Surface / coating', zh: '表面处理 / 贴材料' }, icon: 'tip-surface', disabled: true },
    ],
  },
  {
    id: 'camera', title: { en: 'Camera', zh: '相机' }, view: 'camera',
    hint: { en: 'The phone or camera on the pusher. Sets the view.', zh: '装在推杆上的手机或相机，决定视野。' },
    items: [
      {
        id: 'iphone17pro', name: 'iPhone 17 Pro', subtitle: { en: 'Apple · landscape', zh: 'Apple · 横屏' }, icon: 'phone',
        info: [
          { label: { en: 'Brand', zh: '品牌' }, value: 'Apple' },
          { label: { en: 'Main', zh: '主摄' }, value: { en: '48 MP Fusion, 24 mm, ƒ/1.78, 2nd-gen sensor-shift OIS', zh: '48 MP Fusion，24 mm，ƒ/1.78，第二代传感器位移防抖' } },
          { label: { en: 'Ultra Wide', zh: '超广角' }, value: { en: '48 MP, 13 mm, ƒ/2.2, 120° FOV', zh: '48 MP，13 mm，ƒ/2.2，120° 视场' } },
          { label: { en: 'Telephoto', zh: '长焦' }, value: '48 MP, 100 mm (4×), ƒ/2.8' },
          { label: { en: 'Max frame rate', zh: '最高帧率' }, value: { en: '4K 120 fps (main), 1080p slo-mo 240 fps', zh: '4K 120 fps（主摄），1080p 慢动作 240 fps' } },
          { label: { en: 'Sensor size', zh: '传感器尺寸' }, value: { en: 'not published by Apple', zh: '官方未公布' }, verify: true },
          { label: { en: 'Min focus distance', zh: '最近对焦距离' }, value: { en: 'not published, to measure', zh: '官方未公布，需实测' }, verify: true },
          { label: { en: 'Body', zh: '机身' }, value: '150 × 71.9 × 8.75 mm, 206 g' },
        ],
        links: [
          { label: { en: 'Apple tech specs', zh: 'Apple 官方技术规格' }, url: 'https://support.apple.com/125090' },
          { label: { en: 'Apple dimensional drawings (for accessory makers)', zh: 'Apple 尺寸图（配件厂商用）' }, url: 'https://developer.apple.com/accessories/dimensional-drawings/' },
        ],
      },
      { id: 'realsense', name: 'Intel RealSense', icon: 'depthcam', disabled: true },
      { id: 'other_phone', name: { en: 'Other phones', zh: '其他手机' }, icon: 'phone', disabled: true },
    ],
  },
];

export const DEFAULT_SELECTION: Record<string, string> = { carrier: 'rebot_rs', adapter: 'gripper_ab', pusher: 'rod_v1', tip: 'bare', camera: 'iphone17pro' };

export function item(groupId: string, id: string): CatalogItem | undefined {
  return GROUPS.find((g) => g.id === groupId)?.items.find((i) => i.id === id);
}

/** Whether an adapter can be used with a carrier. */
export function fits(adapter: CatalogItem | undefined, carrierId: string): boolean {
  return !!adapter && !adapter.disabled && (!adapter.fits || adapter.fits.includes(carrierId));
}
