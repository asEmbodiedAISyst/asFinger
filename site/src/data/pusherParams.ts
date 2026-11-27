// How the pusher parameters are presented. Parameters not listed here still appear under "Other".
// `advanced` = hidden until "Advanced" is ticked: the panel starts with the few values most people change
// (for the rod: its length and tilt) and uses the config values for the rest.
// `owner` = which group decides the value (then it is read-only in the pusher panel, in section 'owned').
// Carrier-owned values (the hole pattern of the pusher base) become editable when the carrier is "Custom flange".
import type { Txt } from '../i18n';

export interface ParamMeta {
  label: Txt; unit?: string; min?: number; max?: number; step?: number; hint?: Txt;
  section: SectionId; owner?: 'carrier' | 'adapter' | 'camera' | 'tip'; advanced?: boolean; slider?: boolean;
}

export type SectionId = 'install' | 'rod' | 'flange' | 'aim' | 'link' | 'mount' | 'owned' | 'other';
export const SECTIONS: { id: SectionId; title: Txt }[] = [
  { id: 'install', title: { en: 'Mounting on the flange', zh: '在法兰上的安装' } },
  { id: 'rod', title: { en: 'Rod', zh: '推杆' } },
  { id: 'flange', title: { en: 'Base hole pattern (custom flange)', zh: '底座孔位（自定义法兰）' } },
  { id: 'aim', title: { en: 'Camera looks at the TCP (solved)', zh: '相机看向 TCP（求解）' } },
  { id: 'link', title: { en: 'Connectors', zh: '连接件' } },
  { id: 'mount', title: { en: 'Phone mount', zh: '手机安装' } },
  { id: 'owned', title: { en: 'Set by other groups', zh: '由其它组决定' } },
  { id: 'other', title: { en: 'Other', zh: '其它' } },
];

export const PARAMS: Record<string, ParamMeta> = {
  mount_rot: { label: { en: 'Mounting angle', zh: '安装转角' }, unit: '°', min: -180, max: 180, step: 1, section: 'install', slider: true, hint: { en: 'Turn of the pusher about the flange axis: from +X of the robot flange to the side the rod leans to. The default comes from the carrier, so that every arm carries the phone on top. The holes in the base stay on the flange pattern.', zh: '推杆绕法兰轴线转过的角度：从机械臂法兰的 +X 到杆倾斜的那一侧。默认值由载体给出，让每种机械臂装上后都是手机在上。底座上的孔始终对着法兰孔位。' } },
  key_L: { label: { en: 'Hex key clearance', zh: '内六角扳手净空' }, unit: 'mm', min: 5, max: 60, step: 1, section: 'install', advanced: true, hint: { en: 'Free height needed above each screw head for the short arm of an L-key (checked, blocks export)', zh: '每个螺钉头上方要留给 L 形扳手短边的高度（做检查，不满足不能导出）' } },
  key_d: { label: { en: 'Key / driver diameter', zh: '扳手 / 螺丝刀直径' }, unit: 'mm', min: 2, max: 12, step: 0.5, section: 'install', advanced: true },
  driver_L: { label: { en: 'Straight driver length', zh: '直螺丝刀长度' }, unit: 'mm', min: 30, max: 250, step: 5, section: 'install', advanced: true, hint: { en: 'Screws a straight driver of this length cannot reach are reported as a note only', zh: '这个长度的直螺丝刀够不到的螺钉只作提示' } },

  rod_L: { label: { en: 'Rod length', zh: '杆长' }, unit: 'mm', min: 80, max: 260, step: 0.5, section: 'rod', slider: true },
  rod_D: { label: { en: 'Rod diameter', zh: '杆径' }, unit: 'mm', min: 8, max: 25, step: 0.5, section: 'rod', slider: true, advanced: true, hint: { en: 'The ball tip radius follows (= diameter / 2)', zh: '球头半径跟着变（= 杆径 / 2）' } },
  rod_w: { label: { en: 'Rod width', zh: '杆宽' }, unit: 'mm', min: 6, max: 25, step: 0.5, section: 'rod', slider: true, advanced: true, hint: { en: 'Side of the square rod', zh: '方杆的边长' } },
  rod_tilt: { label: { en: 'Rod tilt', zh: '杆倾角' }, unit: '°', min: 0, max: 60, step: 0.5, section: 'rod', slider: true, hint: { en: 'Relative to the flange axis', zh: '相对法兰轴线' } },
  rod_x: { label: { en: 'Rod root offset', zh: '杆根偏移' }, unit: 'mm', min: -15, max: 20, step: 0.1, section: 'rod', advanced: true, hint: { en: 'Distance along X from the base centre to the rod root centre', zh: '杆根中心到底座中心沿 X 的距离' } },

  phone_flange_angle: { label: { en: 'Phone mount angle', zh: '手机安装面角度' }, unit: '°', min: 20, max: 90, step: 0.1, section: 'aim', slider: true, hint: { en: 'Angle between the optical axis and the flange axis', zh: '光轴与法兰轴线的夹角' } },
  v_n: { label: { en: 'TCP vertical position in the image', zh: 'TCP 在画面中的纵向位置' }, min: -0.9, max: 0.9, step: 0.001, section: 'aim', slider: true, hint: { en: '−1 bottom edge, 0 centre, +1 top edge; golden ratio = −0.236', zh: '-1 底边，0 中心，+1 顶边；黄金分割 = -0.236' } },
  distance: { label: { en: 'Lens to TCP distance', zh: '镜头到 TCP 距离' }, unit: 'mm', min: 60, max: 320, step: 0.5, section: 'aim', slider: true, hint: { en: 'Keep it above the minimum focus distance', zh: '不要小于最近对焦距离' } },

  beam_w: { label: { en: 'Beam width', zh: '横梁宽度' }, unit: 'mm', min: 6, max: 20, step: 0.5, section: 'link' },
  spine_w: { label: { en: 'Spine width', zh: '支撑条宽度' }, unit: 'mm', min: 15, max: 60, step: 0.5, section: 'link' },
  plate_t: { label: { en: 'Plate thickness', zh: '板厚' }, unit: 'mm', min: 5, max: 16, step: 0.5, section: 'link' },
  spine_top: { label: { en: 'Spine start', zh: '支撑条起点' }, unit: 'mm', min: -60, max: 0, step: 0.5, section: 'link', advanced: true },
  spine_overlap: { label: { en: 'Spine overlap into the clip', zh: '支撑条伸入卡扣' }, unit: 'mm', min: 0, max: 3, step: 0.1, section: 'link', advanced: true },
  spine_back: { label: { en: 'Reinforce the holder joint', zh: '加固支撑板连接处' }, min: 0, max: 1, step: 1, section: 'link', hint: { en: '1 = continue the spine up the back of the holder into the X ribs, so the thin back plate at the joint is not bent; 0 = old butt joint', zh: '1 = 支撑条沿支撑板背面延伸到十字加强筋上，连接处不再只靠几毫米的背板受力；0 = 旧的对接方式' } },
  spine_back_to: { label: { en: 'Reinforcement tip (X-rib crossing)', zh: '加固端点（十字筋交叉点）' }, unit: 'mm', min: -30, max: 30, step: 0.05, section: 'link', advanced: true, hint: { en: 'Along the holder plate from the MagSafe centre; the V end of the reinforcement points here', zh: '沿支撑板、从 MagSafe 中心量起；加固部分的 V 形尖端在这里' } },
  spine_back_ang: { label: { en: 'X-rib arm angle', zh: '十字筋臂角度' }, unit: '°', min: 10, max: 80, step: 0.1, section: 'link', advanced: true, hint: { en: 'Angle between each lower arm of the X ribs and the spine; the reinforcement is cut along both arms', zh: '十字筋下方两条臂与支撑条轴线的夹角；加固部分沿这两条臂切成 V 形' } },
  spine_back_w: { label: { en: 'Reinforcement width', zh: '加固宽度' }, unit: 'mm', min: 10, max: 60, step: 0.5, section: 'link', advanced: true },
  holder_back_z: { label: { en: 'Holder plate back face', zh: '支撑板背面位置' }, unit: 'mm', min: -10, max: 0, step: 0.1, section: 'link', advanced: true, hint: { en: 'Depth of the back face of the holder plate below the mount surface (from the holder model)', zh: '支撑板背面在安装面以下的深度（由支架模型决定）' } },
  beam_x: { label: { en: 'Beam X position', zh: '横梁 X 位置' }, unit: 'mm', min: -15, max: 25, step: 0.5, section: 'link', advanced: true },
  beam_y_in: { label: { en: 'Beam start Y', zh: '横梁起点 Y' }, unit: 'mm', min: -10, max: 20, step: 0.5, section: 'link', advanced: true },

  back_to_mount: { label: { en: 'Phone back to mount plate', zh: '手机背面到支撑板' }, unit: 'mm', min: 0, max: 10, step: 0.1, section: 'mount', hint: { en: 'Case thickness + clearance', zh: '手机壳厚度 + 间隙' } },

  base_R: { label: { en: 'Base radius', zh: '底座半径' }, unit: 'mm', min: 10, max: 60, step: 0.1, section: 'flange', owner: 'carrier' },
  base_t: { label: { en: 'Base thickness', zh: '底座厚度' }, unit: 'mm', min: 6, max: 16, step: 0.5, section: 'link', advanced: true },
  hole_pcd: { label: { en: 'Screw PCD', zh: '螺钉节圆' }, unit: 'mm', min: 10, max: 100, step: 0.01, section: 'flange', owner: 'carrier', hint: { en: 'Diameter of the circle through the 4 screw holes', zh: '4 个螺钉孔所在圆的直径' } },
  hole_rot: { label: { en: 'Hole pattern angle', zh: '孔位角度' }, unit: '°', min: -180, max: 180, step: 0.5, section: 'flange', owner: 'carrier', hint: { en: 'First hole, measured from +X of the robot flange frame', zh: '第一个孔相对机械臂法兰坐标系 +X 的角度' } },
  hole_ang2: { label: { en: 'Angle to the second hole', zh: '到第二个孔的夹角' }, unit: '°', min: 10, max: 170, step: 0.5, section: 'flange', owner: 'carrier', hint: { en: '90 = square pattern; the other two holes are opposite', zh: '90 = 正方形排布；另外两个孔在对面' } },
  hole_d: { label: { en: 'Screw hole', zh: '螺钉孔径' }, unit: 'mm', min: 1, max: 12, step: 0.1, section: 'flange', owner: 'carrier' },
  cbore_d: { label: { en: 'Counterbore diameter', zh: '沉孔直径' }, unit: 'mm', min: 2, max: 20, step: 0.1, section: 'flange', owner: 'carrier' },
  cbore_depth: { label: { en: 'Counterbore depth', zh: '沉孔深度' }, unit: 'mm', min: 0, max: 12, step: 0.1, section: 'flange', owner: 'carrier' },
  screw_head_d: { label: { en: 'Screw head diameter', zh: '螺钉头直径' }, unit: 'mm', min: 2, max: 20, step: 0.1, section: 'flange', owner: 'carrier', advanced: true },
  screw_head_h: { label: { en: 'Screw head height', zh: '螺钉头高度' }, unit: 'mm', min: 1, max: 12, step: 0.1, section: 'flange', owner: 'carrier', advanced: true },
  relief_h: { label: { en: 'Relief depth', zh: '让位深度' }, unit: 'mm', min: 0, max: 5, step: 0.1, section: 'flange', owner: 'carrier', advanced: true, hint: { en: 'Pocket in the base face for things that stand proud of the flange (0 = none)', zh: '底座安装面上给法兰端面凸出物留的让位（0 = 不留）' } },
  relief_c_d: { label: { en: 'Relief: centre diameter', zh: '让位：中心直径' }, unit: 'mm', section: 'flange', owner: 'carrier', advanced: true },
  relief_p_d: { label: { en: 'Relief: pin diameter', zh: '让位：销直径' }, unit: 'mm', section: 'flange', owner: 'carrier', advanced: true },
  relief_p_r: { label: { en: 'Relief: pin circle radius', zh: '让位：销所在半径' }, unit: 'mm', section: 'flange', owner: 'carrier', advanced: true },
  relief_p_rot: { label: { en: 'Relief: first pin angle', zh: '让位：第一个销角度' }, unit: '°', section: 'flange', owner: 'carrier', advanced: true },
  adapter_h: { label: { en: 'Adapter height', zh: '转接件高度' }, unit: 'mm', section: 'owned', owner: 'adapter', hint: { en: 'Robot flange face to pusher base face', zh: '机械臂法兰面到推杆底座安装面' } },
  mount_screws: { label: { en: 'Base screws', zh: '底座螺钉方式' }, section: 'owned', owner: 'adapter', hint: { en: '0 = none (cup printed in), 1 = from the adapter side into blind holes, 2 = from the tool side through counterbored holes', zh: '0 = 没有（杯形一体打印），1 = 从转接件一侧拧进盲孔，2 = 从工具一侧穿过沉孔' } },
  hole_len: { label: { en: 'Hole length (derived)', zh: '孔长（推导）' }, unit: 'mm', section: 'owned', owner: 'adapter' },
  hole_depth: { label: { en: 'Blind hole depth', zh: '盲孔深度' }, unit: 'mm', section: 'owned', owner: 'adapter' },
  phone_W: { label: { en: 'Phone width', zh: '手机宽' }, unit: 'mm', section: 'owned', owner: 'camera' },
  phone_L: { label: { en: 'Phone length', zh: '手机长' }, unit: 'mm', section: 'owned', owner: 'camera' },
  phone_t: { label: { en: 'Phone thickness', zh: '手机厚' }, unit: 'mm', section: 'owned', owner: 'camera' },
  lens_x: { label: { en: 'Main lens X', zh: '主摄 X' }, unit: 'mm', section: 'owned', owner: 'camera' },
  lens_y: { label: { en: 'Main lens Y', zh: '主摄 Y' }, unit: 'mm', section: 'owned', owner: 'camera' },
  bump_h: { label: { en: 'Camera glass height', zh: '镜头玻璃高度' }, unit: 'mm', section: 'owned', owner: 'camera', hint: { en: 'Rear camera cover glass above the back glass: camera plateau + lens glass', zh: '后摄镜头玻璃高出背面玻璃的高度：镜头平台 + 镜头玻璃' } },
  ring_D: { label: { en: 'Lens window diameter', zh: '镜头窗口直径' }, unit: 'mm', section: 'owned', owner: 'camera' },
  corner_r: { label: { en: 'Body corner radius (estimate)', zh: '机身圆角半径（估计值）' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  outline_x: { label: { en: 'Phone outline centre X', zh: '手机外形中心 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  outline_y: { label: { en: 'Phone outline centre Y', zh: '手机外形中心 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  uw_x: { label: { en: 'Ultra Wide X', zh: '超广角 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  uw_y: { label: { en: 'Ultra Wide Y', zh: '超广角 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  tele_x: { label: { en: 'Telephoto X', zh: '长焦 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  tele_y: { label: { en: 'Telephoto Y', zh: '长焦 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  front_x: { label: { en: 'Front camera X', zh: '前摄 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  front_y: { label: { en: 'Front camera Y', zh: '前摄 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  lidar_x: { label: { en: 'LiDAR X', zh: 'LiDAR X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  lidar_y: { label: { en: 'LiDAR Y', zh: 'LiDAR Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  flash_x: { label: { en: 'Flash X', zh: '闪光灯 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  flash_y: { label: { en: 'Flash Y', zh: '闪光灯 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  magsafe_x: { label: { en: 'MagSafe centre X', zh: 'MagSafe 圆心 X' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  magsafe_y: { label: { en: 'MagSafe centre Y', zh: 'MagSafe 圆心 Y' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  feq_tele: { label: { en: 'Telephoto equivalent focal length', zh: '长焦等效焦距' }, unit: 'mm', section: 'owned', owner: 'camera', advanced: true },
  feq: { label: { en: 'Equivalent focal length', zh: '等效焦距' }, unit: 'mm', section: 'owned', owner: 'camera' },
  tip_R: { label: { en: 'Ball tip radius', zh: '球头半径' }, unit: 'mm', section: 'owned', owner: 'tip' },
  rod_embed: { label: { en: 'Rod root embed depth', zh: '杆根埋入深度' }, unit: 'mm', section: 'other', advanced: true },
};

/** Presentation of a parameter; ones not listed fall back to "Other" (the gripper connector's own dimensions to the adapter). */
export function paramMeta(k: string): ParamMeta {
  return PARAMS[k] ?? (k.startsWith('cup_')
    ? { label: k, unit: k.endsWith('_rot') ? '°' : 'mm', section: 'owned', owner: 'adapter' }
    : { label: k, section: 'other', advanced: true });
}

/** Who may edit a parameter: nobody when a group owns it, except the carrier's flange values on a custom flange. */
export function isLocked(k: string, fixed: Record<string, unknown>, customFlange: boolean): boolean {
  const owner = paramMeta(k).owner;
  return k in fixed || (!!owner && !(owner === 'carrier' && customFlange));
}
