// Two languages: English (default, at /) and Chinese (at /zh/).
// Data files use `Txt` (a plain string when it reads the same in both, else {en, zh});
// UI strings live in `UI` below. Add a language by adding a key to both.
import { createContext, useContext } from 'react';

export type Lang = 'en' | 'zh';
export const LANGS: Lang[] = ['en', 'zh'];
export const DEFAULT_LANG: Lang = 'en';
export const LANG_LABEL: Record<Lang, string> = { en: 'English', zh: '中文' };

/** The product name and the editor's name as people see them. Change them here only: pages, titles, the editor
 *  header and the UI strings below all read these two entries. */
export const PRODUCT: Record<Lang, string> = { en: 'asFinger', zh: 'asFinger' };
export const EDITOR_NAME: Record<Lang, string> = { en: 'asFinger editor', zh: 'asFinger 编辑器' };
/** The Python package and command (`python -m asfinger`); a code name, not translated. */
export const PY_PACKAGE = 'asfinger';

export type Txt = string | { en: string; zh: string };
export const tx = (v: Txt | undefined, lang: Lang): string => (v == null ? '' : typeof v === 'string' ? v : v[lang] ?? v.en);

/** URL of `path` (no leading slash, '' = home) in `lang`, honouring the site base. */
export function langPath(lang: Lang, path = ''): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
  return `${base}${lang === DEFAULT_LANG ? '' : '/' + lang}/${path}`;
}

/** The language a path is in, from its first segment after the base. */
export function langOf(pathname: string): Lang {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
  const seg = pathname.slice(base.length).split('/').filter(Boolean)[0];
  return (LANGS as string[]).includes(seg) ? (seg as Lang) : DEFAULT_LANG;
}

const UI = {
  // shell
  editorTitle: { en: 'editor', zh: '编辑器' },
  docs: { en: 'Docs', zh: '文档' },
  localOnly: { en: 'Your choices and parameters are saved in this browser only', zh: '只在本浏览器里保存你的选择和参数' },
  narrow: { en: 'The editor needs a wide desktop browser window (≥ 1100 px).', zh: '编辑器需要较宽的桌面浏览器窗口（≥ 1100 px）。' },
  // left
  configure: { en: 'Configure', zh: '配置' },
  closePanel: { en: 'Close', zh: '收起' },
  inspect: { en: 'Parameters & info', zh: '参数与信息' },
  planned: { en: 'Planned', zh: '规划中' },
  none: { en: 'None', zh: '未选' },
  notForCarrier: { en: 'Other carrier', zh: '不适用于此载体' },
  // center
  overall: { en: 'Full assembly', zh: '整体预览' },
  soloHint: { en: 'Show only this part', zh: '只看这个部件' },
  soloBack: { en: 'Back to the full assembly', zh: '回到整体' },
  view: { en: 'View', zh: '视角' },
  theme: { en: 'Appearance', zh: '外观' },
  themeSystem: { en: 'Follow the system', zh: '跟随系统' },
  themeLight: { en: 'Light', zh: '浅色' },
  themeDark: { en: 'Dark', zh: '深色' },
  resetView: { en: 'Reset view', zh: '重置视角' },
  units: { en: 'units mm', zh: '单位 mm' },
  noteArm: { en: 'Arm model: {src}, pose {pose} · robot flange frame F_robot (EE)', zh: '机械臂模型：{src}，姿态 {pose} · 标出机械臂法兰坐标系 F_robot（EE）' },
  noteJoint: { en: '{joint} drawn at {deg}°', zh: '{joint} 画在 {deg}°' },
  noteAdapter: { en: 'Robot flange (grey, below) · adapter · pusher translucent · F_robot = robot flange, F_mount = pusher base face, turned by the mounting angle', zh: '机械臂法兰（灰色，在下）· 转接件 · 推杆半透明 · F_robot = 机械臂法兰，F_mount = 推杆底座安装面，两者差一个安装转角' },
  loadingModel: { en: 'Loading the arm model…', zh: '正在加载机械臂模型…' },
  noteCarrier: { en: 'Placeholder model · robot flange frame F_robot (EE)', zh: '示意模型 · 标出机械臂法兰坐标系 F_robot（EE）' },
  notePusher: { en: 'Pusher + phone holder · phone shown translucent · frames F_mount (base face), R_rod, T_tcp, S_mount, P_phone', zh: '推杆 + 手机支架 · 手机半透明作参考 · 标出 F_mount（底座安装面）、R_rod、T_tcp、S_mount、P_phone' },
  noteTip: { en: 'Tip · T_tip (rod end face centre) and T_tcp (ball apex)', zh: '末端 · T_tip（杆端面中心）与 T_tcp（球头顶点）' },
  noteCamera: { en: 'Camera frame C_main (MuJoCo: looks along −Z) and view frustum, far plane at the TCP distance', zh: '相机坐标系 C_main（MuJoCo：看向 -Z）和视野范围，远端面在 TCP 距离处' },
  noteOverall: { en: 'Full assembly: carrier + adapter + pusher + phone, camera view aimed at the TCP', zh: '整体：载体 + 转接件 + 推杆 + 手机，相机视野指向 TCP' },
  imageUp: { en: 'image top', zh: '画面上方' },
  handGrip: { en: 'Hand grip (placeholder)', zh: '手持握把（示意）' },
  // status
  loadingEngine: { en: 'Loading the geometry engine (a few seconds the first time)…', zh: '正在加载几何引擎（第一次打开约需数秒）…' },
  engineFailed: { en: 'Geometry engine failed to load: ', zh: '几何引擎加载失败：' },
  solveFailed: { en: 'Solve failed: ', zh: '求解失败：' },
  updating: { en: 'Updating…', zh: '更新中…' },
  checksFailed: { en: '{n} check(s) failed', zh: '{n} 项检查未通过' },
  updated: { en: 'Updated · {ms} ms', zh: '已更新 · {ms} ms' },
  configLoadFailed: { en: 'Could not load the config: ', zh: '配置加载失败：' },
  exportFailed: { en: 'Export failed: ', zh: '导出失败：' },
  // info
  overallTitle: { en: 'Assembly', zh: '整体' },
  currentPusher: { en: 'Current pusher', zh: '当前推杆' },
  fromParams: { en: 'From current parameters', zh: '按当前参数' },
  notSelected: { en: 'Nothing selected', zh: '未选择' },
  verify: { en: 'to verify', zh: '待核实' },
  volume: { en: 'Volume · {name}', zh: '体积 · {name}' },
  mass: { en: 'Est. mass (PLA, 100% infill)', zh: '估计质量（PLA，100% 填充）' },
  tcpInMount: { en: 'TCP (pusher base F_mount)', zh: 'TCP（推杆底座 F_mount）' },
  tcpInFlange: { en: 'TCP (robot flange F_robot)', zh: 'TCP（机械臂法兰 F_robot）' },
  camInFlange: { en: 'Main camera (robot flange F_robot)', zh: '主摄（机械臂法兰 F_robot）' },
  basePattern: { en: 'Pusher base holes (set by this adapter)', zh: '推杆底座孔位（由这个转接件决定）' },
  baseNoScrews: { en: 'No screws in the pusher base: the cup of connector part B is printed at its bottom and held on part A by the three set screws from the side.', zh: '推杆底座上没有螺钉：零件 B 的杯形直接打印在推杆底部，靠侧面 3 个顶丝固定在零件 A 上。' },
  basePatternNote: { en: 'Seen from the tool side, in the robot flange frame F_robot. The holes stay on this pattern when the mounting angle changes; only the pusher turns over them.', zh: '从工具一侧看，画在机械臂法兰坐标系 F_robot 里。改安装转角时孔位不动，转的是孔上面的推杆。' },
  adapterHeight: { en: 'Flange face to base face', zh: '法兰面到底座安装面' },
  mountAngle: { en: 'Mounting angle', zh: '安装转角' },
  mountNote: { en: 'Mounting note', zh: '安装提示' },
  mountAngleDefault: { en: 'default for {name}: {deg}°', zh: '{name} 的默认值 {deg}°' },
  jointTurn: { en: 'Arm drawn with', zh: '机械臂画法' },
  jointTurnVal: { en: '{joint} at {deg}°, so the phone is still on top', zh: '{joint} 转到 {deg}°，这样手机仍然在上' },
  flangePattern: { en: 'Flange pattern', zh: '法兰孔位' },
  screws: { en: 'Screws', zh: '螺钉' },
  threads: { en: 'Threaded holes', zh: '螺纹孔' },
  threadsVal: { en: '{n} × {t} on Ø{pcd} mm', zh: '{n} × {t}，节圆 Ø{pcd} mm' },
  threadDepth: { en: 'Thread depth', zh: '螺纹孔深度' },
  pilot: { en: 'Centring recess', zh: '定心止口' },
  pin: { en: 'Locating pin', zh: '定位销' },
  source: { en: 'Source: ', zh: '来源：' },
  camInModel: { en: 'Camera in the current model', zh: '当前模型里的相机' },
  vfov: { en: 'Vertical FOV (preview)', zh: '竖直视场（预览用）' },
  frame: { en: 'Image', zh: '画幅' },
  lensToTcp: { en: 'Lens to TCP', zh: '镜头到 TCP' },
  flangeCaption: { en: 'Flange face seen from the tool side; the pin hole is red. Z points at the reader (toward the tool).', zh: '从工具一侧看法兰面；红色为定位销孔。Z 轴指向读者（工具方向）。' },
  pcd: { en: 'PCD Ø{pcd}', zh: '节圆 Ø{pcd}' },
  outer: { en: 'outer Ø{d}', zh: '外径 Ø{d}' },
  // params
  params: { en: 'Parameters', zh: '参数' },
  pusherParams: { en: 'Pusher parameters', zh: '推杆参数' },
  advanced: { en: 'Advanced', zh: '高级' },
  resetAll: { en: 'Reset', zh: '恢复默认' },
  editedReset: { en: '{n} changed from default · reset', zh: '已改 {n} 个参数 · 恢复默认' },
  resetAllHint: { en: 'Reset all parameters to the config values', zh: '所有参数恢复为配置文件里的值' },
  resetOne: { en: 'Reset to default', zh: '恢复默认' },
  readOnly: { en: 'read-only', zh: '只读' },
  decidedBy: { en: 'set by {who}', zh: '由{who}决定' },
  loadingConfig: { en: 'Loading the pusher config…', zh: '正在加载推杆配置…' },
  export: { en: 'Export', zh: '导出' },
  generating: { en: 'Generating…', zh: '生成中…' },
  exportNote: { en: `The config file works with \`python -m ${PY_PACKAGE}\` and the Fusion add-in. While a check fails (amber), only the config can be exported, not STL. The print STL is in the pusher base frame: mounting face on z = 0.`, zh: `配置文件可以直接给 \`python -m ${PY_PACKAGE}\` 或 Fusion 插件使用。有检查未通过（黄色）时只能导出配置，不能导出 STL。打印件 STL 在推杆底座坐标系里：安装面在 z = 0。` },
  exPrint: { en: 'Print STL ({name})', zh: '打印件 STL（{name}）' },
  exPrintHint: { en: 'Pusher and phone holder fused into one body, ready to slice', zh: '推杆和手机支架合成一体，直接切片打印' },
  exConfig: { en: 'Config JSON', zh: '配置 JSON' },
  exConfigHint: { en: `Current parameters and solved frames; loads into ${PY_PACKAGE} / the Fusion add-in`, zh: `当前参数和求解好的坐标系，可再导入 ${PY_PACKAGE} / Fusion 插件` },
  exPart: { en: 'Part {name}.stl', zh: '单件 {name}.stl' },
  exPartHint: { en: 'A single part, in its own frame', zh: '单个零件，在自己的坐标系里' },
  noParamsCarrier: { en: 'Carriers have no parameters. The carrier sets the default mounting angle and, without a mount adapter, the hole pattern of the pusher base; those values appear read-only in the pusher parameters.', zh: '载体没有可调参数。载体决定默认安装转角；不用安装转接件时还决定推杆底座的孔位，这些值在推杆参数里只读显示。' },
  noParamsCamera: { en: 'Phone size and lens position come from the selected model and appear read-only in the pusher parameters. The angle and distance at which the lens looks at the TCP are pusher parameters.', zh: '相机尺寸和镜头位置由所选机型决定，在推杆参数里只读显示。镜头看向 TCP 的角度和距离在推杆参数里调。' },
  noParams: { en: 'This group has no parameters yet.', zh: '这一组暂时没有可调参数。' },
  dragSplit: { en: 'Drag to resize (double-click to reset)', zh: '拖动调整高度（双击恢复）' },
  startFrom: { en: 'Start from', zh: '从标准开始' },
  noteCustom: { en: 'No carrier · custom flange drawn from the base parameters, frame F_robot', zh: '无载体 · 按底座参数画出的自定义法兰，标出 F_robot' },
  goPusher: { en: 'Edit pusher parameters', zh: '去调推杆参数' },
} satisfies Record<string, { en: string; zh: string }>;

export type UIKey = keyof typeof UI;

export function makeT(lang: Lang) {
  return (key: UIKey, vars?: Record<string, string | number>) => {
    let s: string = UI[key][lang];
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
    return s;
  };
}

export const LangContext = createContext<Lang>(DEFAULT_LANG);
export function useI18n() {
  const lang = useContext(LangContext);
  return { lang, t: makeT(lang), tx: (v: Txt | undefined) => tx(v, lang) };
}
