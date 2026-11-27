// Imperative three.js view. React only tells it *what* to show; it never re-creates the renderer.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import ARMS from '../data/arms.json';
import type { PartMesh, Pose, Resolved } from '../engine/types';
import type { CatalogItem, FlangeSpec, JointTurn } from '../data/catalog';
import { customFlangeSpec, holeAngles } from '../data/flanges';
import { makeT, type Lang } from '../i18n';

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Baked arm models (scripts/bake-arms.py): GLB in the arm base frame (mm, posed) + the flange pose in that frame.
 *  The flange frame is the robot's own (the config's F_robot); adapter and pusher are drawn in it. */
export interface ArmModel { file: string; flange: Pose; short: string; pose: string; source: string; url: string; license: string }
export const ARM_MODELS = ARMS as unknown as Record<string, ArmModel>;

/** No animated camera moves when the system asks for reduced motion. */
const STILL = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

const css = (name: string, fallback: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

/** Names shown on the frames. The config keeps its own; the view uses the unified convention for the phone side
 *  (device = Core Motion axes; cameras = OpenCV optical frames: x image right, y image down, z along the view). */
const FRAME_LABEL: Record<string, string> = { P_phone: 'device', C_cv: 'cam_main_optical' };

export function poseMatrix(p: Pose): THREE.Matrix4 {
  const [w, x, y, z] = p.quat;
  return new THREE.Matrix4().compose(new THREE.Vector3(...p.pos), new THREE.Quaternion(x, y, z, w).normalize(), new THREE.Vector3(1, 1, 1));
}

export interface SceneContent {
  /** 'overall' = the full assembly; a group = only that part, in its own frame (isolated) */
  view: 'carrier' | 'adapter' | 'pusher' | 'tip' | 'camera' | 'overall';
  /** full assembly only: the group the camera looks at ('overall' or missing = everything) */
  focus?: string;
  carrier?: CatalogItem;
  adapter?: CatalogItem;
  /** the arm's last joint is drawn turned (a direct mount that needs another mounting angle to reach its screws) */
  joint?: JointTurn;
  /** the carrier's usual mounting angle with this adapter (deg); the full assembly is laid out from it, see TOOL_POSE */
  mountRot?: number;
  result?: { resolved: Resolved; meshes: PartMesh[]; overlaps?: { id: string; positions: Float32Array; indices: Uint32Array; level?: string }[] } | null;
  lang: Lang;
}

/** Full assembly: where the pusher base frame (F_mount, at the carrier's usual mounting angle) sits in the scene.
 *  The pusher is what stays put when the carrier or the adapter changes; the carrier is moved under it. The pose is
 *  the one the reBot holds it in (connector A + B, mount_rot 180), so that arm stands on the grid origin. */
// The parts that make up the pusher (the ones a config has are drawn): body, separate fingertip, PCB cover, the
// readout PCB and the plug stand-in of the tactile finger, and the phone holder.
const PUSHER_PARTS = ['tool_body', 'tip_tpu', 'pcb_cover', 'pcb', 'usb_plug', 'holder'];

const TOOL_POSE = poseMatrix(ARM_MODELS.rebot_rs.flange)
  .multiply(new THREE.Matrix4().makeTranslation(0, 0, 9)).multiply(new THREE.Matrix4().makeRotationZ(Math.PI));

export class SceneView {
  private renderer: THREE.WebGLRenderer;
  private labels: CSS2DRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(35, 1, 1, 20000);
  private controls: OrbitControls;
  private root = new THREE.Group();
  private grid: THREE.GridHelper;
  private ro: ResizeObserver;
  private raf = 0;
  private lastView = '';            // what the camera was last framed on (see update)
  private lastScene = '';           // the view it was framed in
  private fitted = false;
  private last: SceneContent | null = null;
  private fly: { t0: number; ms: number; p0: THREE.Vector3; p1: THREE.Vector3; c0: THREE.Vector3; c1: THREE.Vector3 } | null = null;
  // Floating panels cover part of the canvas: `inset` is what they cover (px), `shift` moves the picture so the
  // model sits in the middle of what is left (eased, so opening a panel slides the model aside).
  private inset = { l: 0, r: 0, t: 0, b: 0 };
  private shift = new THREE.Vector2();
  private armCache = new Map<string, THREE.Object3D | 'loading' | 'error'>();
  // The part being configured is outlined in the full assembly. The outline needs a post-processing chain; frames
  // without an outline are drawn directly, as before.
  private composer: EffectComposer;
  private outline: OutlinePass;

  constructor(private host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(this.renderer.domElement);
    this.labels = new CSS2DRenderer();
    this.labels.domElement.className = 'labels';
    host.appendChild(this.labels.domElement);
    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.addEventListener('start', () => { this.fly = null; });   // the user takes over
    this.scene.background = new THREE.Color(css('--viewport-bg', '#f0f0ec'));
    // Light: a soft studio environment (gives the metal and gloss of the arm materials something to reflect), a
    // little sky/ground fill and one key light. Neutral tone mapping keeps the part colours as designed.
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.6;
    pmrem.dispose();
    this.renderer.toneMapping = THREE.NeutralToneMapping;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8a80, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(300, -400, 800);
    this.scene.add(sun);
    this.grid = this.makeGrid();
    this.scene.add(this.grid, this.root);
    this.composer = new EffectComposer(this.renderer, new THREE.WebGLRenderTarget(1, 1, { samples: 4, type: THREE.HalfFloatType }));
    this.composer.setPixelRatio(this.renderer.getPixelRatio());
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.outline = new OutlinePass(new THREE.Vector2(1, 1), this.scene, this.camera);
    this.outline.edgeStrength = 5; this.outline.edgeThickness = 1.5; this.outline.edgeGlow = 0;
    // The pass adds its colour to the picture, which all but disappears on a light background: draw it over the
    // picture instead (the edge texture is colour x coverage, so it is already premultiplied).
    const over = this.outline.overlayMaterial;
    over.fragmentShader = over.fragmentShader.replace('gl_FragColor = finalColor;', 'gl_FragColor = clamp(finalColor, 0.0, 1.0);');
    over.blending = THREE.CustomBlending; over.blendSrc = THREE.OneFactor; over.blendDst = THREE.OneMinusSrcAlphaFactor;
    this.composer.addPass(this.outline);
    this.composer.addPass(new OutputPass());
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
    const loop = () => { this.raf = requestAnimationFrame(loop); this.step(); this.controls.update(); this.render(); };
    loop();
  }

  /** The colour tokens changed (light / dark): take the new background and grid, and draw the parts again. */
  retheme() {
    (this.scene.background as THREE.Color).set(css('--viewport-bg', '#f0f0ec'));
    this.scene.remove(this.grid);
    this.grid.geometry.dispose(); (this.grid.material as THREE.Material).dispose();
    this.grid = this.makeGrid();
    this.scene.add(this.grid);
    if (this.last) this.update(this.last);   // also puts the grid where it was
  }

  private makeGrid(): THREE.GridHelper {
    const g = new THREE.GridHelper(2400, 96, css('--grid', '#d6d6cf'), css('--grid', '#d6d6cf'));
    g.rotation.x = Math.PI / 2;
    return g;
  }

  dispose() {
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.clear();
    this.outline.dispose(); this.composer.dispose();
    this.renderer.dispose();
    this.host.innerHTML = '';
  }

  private resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
    this.labels.setSize(w, h);
    this.camera.aspect = w / h;
    this.applyShift();
  }

  /** What the floating panels cover on each side of the canvas, in px. */
  setInsets(l: number, r: number, t: number, b: number) { this.inset = { l, r, t, b }; }

  private applyShift() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!w || !h) return;
    this.camera.setViewOffset(w, h, -this.shift.x, -this.shift.y, w, h);   // also updates the projection
  }

  /** Per frame: ease the picture shift and a running camera move. */
  private step() {
    const goal = new THREE.Vector2((this.inset.l - this.inset.r) / 2, (this.inset.t - this.inset.b) / 2);
    if (this.shift.distanceTo(goal) > 0.25) { this.shift.lerp(goal, STILL ? 1 : 0.2); this.applyShift(); }
    if (this.fly) {
      const f = this.fly, k = Math.min(1, (performance.now() - f.t0) / f.ms), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      this.camera.position.lerpVectors(f.p0, f.p1, e);
      this.controls.target.lerpVectors(f.c0, f.c1, e);
      if (k >= 1) this.fly = null;
    }
  }

  private render() {
    if (this.outline.selectedObjects.length) this.composer.render(); else this.renderer.render(this.scene, this.camera);
    this.labels.render(this.scene, this.camera);
  }

  private clear() {
    this.root.traverse((o: any) => {
      if (o.userData.keep) return;   // cached arm models are reused across updates
      o.geometry?.dispose?.();
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m: any) => m?.dispose?.());
      if (o instanceof CSS2DObject) o.element.remove();
    });
    this.root.clear();
  }

  // ------------------------------------------------------------- building blocks
  private partMesh(m: PartMesh, opts: { color?: string; opacity?: number } = {}): THREE.Mesh {
    let g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(m.positions, 3));
    g.setIndex(new THREE.BufferAttribute(m.indices, 1));
    g = g.toNonIndexed();
    g.computeVertexNormals();
    const color = opts.color || (m.role === 'reference' ? css('--part-reference', '#c9c9c2') : m.color || css('--part-printed', '#9aa3b2'));
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0.05, flatShading: true,
      transparent: (opts.opacity ?? 1) < 1, opacity: opts.opacity ?? 1, depthWrite: (opts.opacity ?? 1) >= 1 });
    const mesh = new THREE.Mesh(g, mat);
    mesh.name = m.name;
    return mesh;
  }

  private frame(name: string, M: THREE.Matrix4, len: number, strong = true, labelAt = 0.1): THREE.Group {
    const g = new THREE.Group();
    g.applyMatrix4(M);
    const cols = [css('--axis-x', '#d64541'), css('--axis-y', '#3a9d4c'), css('--axis-z', '#2f6fd6')];
    const dirs = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)];
    dirs.forEach((d, i) => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), d.clone().multiplyScalar(len)]);
      const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: cols[i], depthTest: false, transparent: true, opacity: strong ? 1 : 0.55 }));
      line.renderOrder = 10;
      g.add(line);
      const cone = new THREE.Mesh(new THREE.ConeGeometry(len * 0.06, len * 0.18, 12), new THREE.MeshBasicMaterial({ color: cols[i], depthTest: false }));
      cone.position.copy(d.clone().multiplyScalar(len));
      cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d);
      cone.renderOrder = 10;
      g.add(cone);
    });
    const el = document.createElement('div');
    el.className = 'frame-label' + (strong ? '' : ' weak');
    el.textContent = FRAME_LABEL[name] ?? name;
    const lab = new CSS2DObject(el);
    lab.position.set(len * labelAt, len * labelAt, len * labelAt);
    g.add(lab);
    return g;
  }

  private frustum(resolved: Resolved, camName: string, far: number): THREE.Group {
    const c = resolved.cameras[camName];
    const f = resolved.frames[camName];
    const g = new THREE.Group();
    if (!c || !f) return g;
    g.applyMatrix4(poseMatrix(f.world));
    const h = Math.tan((c.fovy_deg * Math.PI) / 360) * far, w = h * (c.aspect || 4 / 3);
    const P = [new THREE.Vector3(-w, -h, -far), new THREE.Vector3(w, -h, -far), new THREE.Vector3(w, h, -far), new THREE.Vector3(-w, h, -far)];
    const O = new THREE.Vector3();
    const pts = [O, P[0], O, P[1], O, P[2], O, P[3], P[0], P[1], P[1], P[2], P[2], P[3], P[3], P[0]];
    const col = css('--accent', '#2f5bd3');
    g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.8 })));
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(2 * w, 2 * h), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }));
    plane.position.z = -far;
    g.add(plane);
    // "up" tick on the top edge, so image orientation is visible
    g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, h, -far), new THREE.Vector3(0, h * 1.15, -far)]), new THREE.LineBasicMaterial({ color: col })));
    const el = document.createElement('div'); el.className = 'frame-label accent'; el.textContent = this.t('imageUp');
    const lab = new CSS2DObject(el); lab.position.set(0, h * 1.2, -far); g.add(lab);
    return g;
  }

  /** The real arm from its baked GLB. Loads it on first use and redraws when it arrives; null = no model, use the fallback. */
  private realArm(item: CatalogItem): { group: THREE.Group; flange: THREE.Matrix4; loading?: boolean } | null {
    const a = ARM_MODELS[item.id];
    const cached = this.armCache.get(item.id);
    if (!a || cached === 'error') return null;
    const group = new THREE.Group();
    if (cached instanceof THREE.Object3D) group.add(cached);
    else if (!cached) {
      this.armCache.set(item.id, 'loading');
      // re-frame once the arm is there (keeping the direction if the user already had a view)
      const redraw = () => { if (this.last?.carrier?.id === item.id) { this.lastView = this.fitted ? '~' : ''; this.update(this.last); } };
      new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(`${BASE}/${a.file}`, (gltf) => {   // the GLBs are meshopt-compressed (bake-arms.py)
        gltf.scene.traverse((o) => { o.userData.keep = true; });
        this.armCache.set(item.id, gltf.scene);
        redraw();
      }, undefined, () => { this.armCache.set(item.id, 'error'); redraw(); });
    }
    return { group, flange: poseMatrix(a.flange), loading: !(cached instanceof THREE.Object3D) };
  }

  private carrierModel(item: CatalogItem, joint?: JointTurn): { group: THREE.Group; flange: THREE.Matrix4; loading?: boolean } {
    if (item.customFlange) return this.customFlange();
    const m = item.id === 'hand' ? this.hand(item) : this.realArm(item) ?? this.arm(item);
    // the last joint turns about the flange axis, so turning it only turns the flange frame (the rotor is not drawn)
    if (joint) m.flange.multiply(new THREE.Matrix4().makeRotationZ((joint.flangeDeg * Math.PI) / 180));
    return m;
  }

  /** No carrier: only the flange face the pusher base screws onto, drawn from the current base parameters. */
  private customFlange(): { group: THREE.Group; flange: THREE.Matrix4 } {
    const g = new THREE.Group();
    const P = this.last?.result?.resolved.params;
    const flange = new THREE.Matrix4();
    if (P) g.add(this.flangeDisc(customFlangeSpec(P), flange, 6));
    return { group: g, flange };
  }

  /** Fallback arm (no baked model, or it failed to load): simple links ending in a flange that points down. */
  private arm(item: CatalogItem): { group: THREE.Group; flange: THREE.Matrix4 } {
    const g = new THREE.Group();
    const R = item.arm?.reach ?? 700;
    const mat = new THREE.MeshStandardMaterial({ color: css('--part-robot', '#d9d9d4'), roughness: 0.85 });
    const joint = new THREE.MeshStandardMaterial({ color: '#5a5f6a', roughness: 0.6 });
    const F = new THREE.Vector3(0.5 * R, 0, 0.42 * R);
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0.22 * R), new THREE.Vector3(0.12 * R, 0, 0.62 * R),
      new THREE.Vector3(F.x, 0, F.z + 0.16 * R), new THREE.Vector3(F.x, 0, F.z)];
    const rad = [0.075 * R, 0.06 * R, 0.05 * R, 0.042 * R];
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.09 * R, 0.1 * R, 0.05 * R, 40), mat);
    base.rotation.x = Math.PI / 2; base.position.z = 0.025 * R; g.add(base);
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1], len = a.distanceTo(b);
      const link = new THREE.Mesh(new THREE.CylinderGeometry(rad[i] * 0.8, rad[i], len, 32), mat);
      link.position.copy(a.clone().add(b).multiplyScalar(0.5));
      link.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
      g.add(link);
      const j = new THREE.Mesh(new THREE.SphereGeometry(rad[i] * 1.05, 24, 16), joint);
      j.position.copy(b); g.add(j);
    }
    // flange frame: origin on the flange face, +Z out of the flange (down), +X along world X
    const flange = new THREE.Matrix4().makeRotationX(Math.PI).setPosition(F.x, 0, F.z - 0.02 * R);
    g.add(this.flangeDisc(item.flange, flange, 0.02 * R));
    return { group: g, flange };
  }

  private hand(item: CatalogItem): { group: THREE.Group; flange: THREE.Matrix4 } {
    const g = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color: css('--part-robot', '#d9d9d4'), roughness: 0.85 });
    const grip = new THREE.Mesh(new THREE.CapsuleGeometry(17, 110, 8, 32), mat);
    grip.rotation.x = Math.PI / 2; grip.position.z = -80; g.add(grip);
    const flange = new THREE.Matrix4();
    g.add(this.flangeDisc(item.flange, flange, 8));
    const el = document.createElement('div'); el.className = 'frame-label weak'; el.textContent = this.t('handGrip');
    const lab = new CSS2DObject(el); lab.position.set(30, 0, -150); g.add(lab);
    return { group: g, flange };
  }

  private flangeDisc(spec: FlangeSpec | undefined, M: THREE.Matrix4, t: number): THREE.Group {
    const g = new THREE.Group();
    g.applyMatrix4(M);
    const r = (spec?.outerD ?? (spec ? spec.pcd + 18 : 60)) / 2;
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(r, r, t, 48), new THREE.MeshStandardMaterial({ color: '#7d828c', roughness: 0.5 }));
    disc.rotation.x = Math.PI / 2; disc.position.z = -t / 2; g.add(disc);
    if (spec) {
      const ring = (cx: number, cy: number, rr: number, color: string) => {
        const pts = Array.from({ length: 33 }, (_, i) => new THREE.Vector3(cx + rr * Math.cos((i / 32) * 2 * Math.PI), cy + rr * Math.sin((i / 32) * 2 * Math.PI), 0.3));
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color })));
      };
      const dia = parseFloat(spec.thread.replace(/[^0-9.]/g, '')) || 4;
      for (const deg of holeAngles(spec)) {
        const a = (deg * Math.PI) / 180;
        ring((spec.pcd / 2) * Math.cos(a), (spec.pcd / 2) * Math.sin(a), dia / 2, '#1b1d22');
      }
      if (spec.pin) { const a = (spec.pin.deg * Math.PI) / 180; ring((spec.pin.pcd / 2) * Math.cos(a), (spec.pin.pcd / 2) * Math.sin(a), spec.pin.d / 2, '#c0392b'); }
      if (spec.pilot) ring(0, 0, spec.pilot.d / 2, '#1b1d22');
    }
    return g;
  }

  /** Overlapping volumes (failed interference rules), drawn on top so they show through the parts: red = must be fixed,
   *  amber = a note. Notes are only marked while the flange adapter is looked at (its info lists them). */
  private overlapMeshes(c: SceneContent): THREE.Group {
    const g = new THREE.Group();
    const notes = c.view === 'adapter' || (c.view === 'overall' && c.focus === 'adapter');
    for (const o of c.result?.overlaps ?? []) {
      if (o.level === 'warn' && !notes) continue;
      let geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(o.positions, 3));
      geo.setIndex(new THREE.BufferAttribute(o.indices, 1));
      geo = geo.toNonIndexed(); geo.computeVertexNormals();
      const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: o.level === 'warn' ? css('--warn', '#b7791f') : css('--danger', '#d63b3b'), transparent: true, opacity: o.level === 'warn' ? 0.45 : 0.75, depthTest: false }));
      mesh.renderOrder = 10; mesh.name = 'overlap:' + o.id;
      g.add(mesh);
    }
    return g;
  }

  // ------------------------------------------------------------- views
  private t = makeT('en');

  update(c: SceneContent) {
    this.t = makeT(c.lang);
    this.last = c;
    this.clear();
    const res = c.result;
    const meshes = res?.meshes ?? [];
    const R = res?.resolved;
    const byName = (n: string) => meshes.find((m) => m.name === n);
    const F = (n: string) => (R?.frames[n] ? poseMatrix(R.frames[n].world) : null);
    const addFrames = (names: string[], len: number, parent: THREE.Object3D = this.root) =>
      names.forEach((n) => { const M = F(n); if (M) parent.add(this.frame(n, M, len)); });
    let focus: THREE.Box3 | null = null;
    let fitDir: THREE.Vector3 | undefined;
    this.grid.visible = true;
    this.grid.position.z = 0;
    const marked: THREE.Object3D[] = [];   // outlined: the part being configured (full assembly only)
    const boxOf = (o: THREE.Object3D) => { this.root.updateMatrixWorld(true); return new THREE.Box3().setFromObject(o); };
    // The pusher, tip and camera views are drawn in the pusher's own frame F_mount (base face on the grid, the rod
    // leaning to +X), whatever adapter and mounting angle put it on the robot.
    const Mt = F('F_mount')?.invert() ?? new THREE.Matrix4();
    const toolGroup = () => { const g = new THREE.Group(); g.applyMatrix4(Mt); this.root.add(g); return g; };

    if (c.view === 'carrier' && c.carrier) {
      const { group, flange } = this.carrierModel(c.carrier, c.joint);
      this.root.add(group);
      const small = c.carrier.id === 'hand' || !!c.carrier.customFlange;
      this.root.add(this.frame(small ? 'F_robot' : 'F_robot (EE)', flange, small ? 40 : 90));
      focus = boxOf(c.carrier.customFlange ? this.root : group);
    }

    if (c.view === 'adapter' && R) {
      // in the robot flange frame: flange face at z = 0, adapter parts on it, the pusher translucent on top
      const spec = c.carrier?.flange ?? (c.carrier?.customFlange ? customFlangeSpec(R.params) : undefined);
      this.root.add(this.flangeDisc(spec, new THREE.Matrix4(), 5));
      for (const m of meshes) if (m.role === 'hardware') this.root.add(this.partMesh(m));
      const body = byName('tool_body'); if (body) this.root.add(this.partMesh(body, { opacity: 0.3 }));
      this.root.add(this.overlapMeshes(c));
      // the two frames can share an origin (no adapter), so the second label sits further out
      addFrames(['F_robot'], 34);
      const Mm = F('F_mount'); if (Mm) this.root.add(this.frame('F_mount', Mm, 26, true, 0.6));
      const h = R.params.adapter_h ?? 0;
      focus = new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(0, 0, h / 2 + 8), new THREE.Vector3(120, 120, 60));
      this.grid.visible = false;
    }

    if ((c.view === 'pusher' || c.view === 'tip') && R) {
      const tg = toolGroup();
      const g = new THREE.Group();
      for (const n of PUSHER_PARTS) { const m = byName(n); if (m) g.add(this.partMesh(m, m.role === 'reference' ? { color: '#3c4048' } : {})); }
      const ph = byName('phone'); if (ph) g.add(this.partMesh(ph, { opacity: 0.25 }));
      tg.add(g);
      tg.add(this.overlapMeshes(c));
      if (c.view === 'pusher') {
        addFrames(['F_mount', 'R_rod', 'T_tcp', 'S_mount', 'P_phone'], 22, tg);
        focus = boxOf(g);
      } else {
        addFrames(['T_tip', 'T_tcp'], 14, tg);
        const p = new THREE.Vector3(...R.frames.T_tcp.world.pos).applyMatrix4(Mt);
        focus = new THREE.Box3().setFromCenterAndSize(p, new THREE.Vector3(60, 60, 60));
      }
    }

    if (c.view === 'camera' && R) {
      const tg = toolGroup();
      const ph = byName('phone'); if (ph) tg.add(this.partMesh(ph, { color: '#3c4048' }));
      tg.add(this.overlapMeshes(c));
      addFrames(['P_phone', 'C_cv'], 25, tg);
      const d = R.params.distance ?? 160;
      tg.add(this.frustum(R, 'C_main', d));
      addFrames(['T_tcp'], 18, tg);
      focus = boxOf(tg);
      this.grid.visible = false;
      const Cm = F('C_main');
      if (!Cm) {
        // no camera chosen: the pusher alone, translucent, so the empty place reads as "nothing here"
        const body = byName('tool_body'); if (body) tg.add(this.partMesh(body, { opacity: 0.3 }));
        focus = boxOf(tg);
      } else {
        // look at the frustum from the side (camera +X) and a little from behind, so the optical axis runs across the screen
        const Mc = Mt.clone().multiply(Cm);
        const ex = new THREE.Vector3().setFromMatrixColumn(Mc, 0), ey = new THREE.Vector3().setFromMatrixColumn(Mc, 1), ez = new THREE.Vector3().setFromMatrixColumn(Mc, 2);
        fitDir = ex.multiplyScalar(1).add(ey.multiplyScalar(0.45)).add(ez.multiplyScalar(0.35));
      }
    }

    if (c.view === 'overall' && c.carrier) {
      const { group, flange: inBase, loading } = this.carrierModel(c.carrier, c.joint);
      // The pusher keeps its place (TOOL_POSE) and the carrier goes under it, so changing the carrier or the adapter
      // changes only that. The arms are baked with the flange pitched alike, so they stay upright (a turn about the
      // vertical and a shift); the grid is the surface the carrier stands on.
      const h = R?.params.adapter_h ?? (c.adapter?.option === false ? 0 : 9);
      const mount0 = new THREE.Matrix4().makeTranslation(0, 0, h).multiply(new THREE.Matrix4().makeRotationZ(((c.mountRot ?? 180) * Math.PI) / 180));
      const flange = TOOL_POSE.clone().multiply(mount0.invert());        // F_robot in the scene
      const place = flange.clone().multiply(inBase.clone().invert());    // the carrier's own frame in the scene
      group.applyMatrix4(place);
      if (ARM_MODELS[c.carrier.id]) this.grid.position.z = place.elements[14];
      this.root.add(group);
      if (c.focus === 'carrier') marked.push(group);
      if (R) {
        // everything the config builds is in the robot flange frame: adapter parts, pusher, holder, phone
        const tool = new THREE.Group();
        tool.applyMatrix4(flange);
        const obj: Record<string, THREE.Object3D> = {};
        for (const m of meshes) tool.add(obj[m.name] = this.partMesh(m, m.role === 'reference' ? { color: '#3c4048' } : {}));
        tool.add(this.overlapMeshes(c));
        addFrames(['T_tcp', 'C_cv'], 35, tool);
        tool.add(this.frustum(R, 'C_main', R.params.distance ?? 160));
        this.root.add(tool);
        this.root.add(this.frame('F_robot', flange, 45, false));
        // The assembly stays whole; the camera goes to the part being configured.
        const around = (names: string[], pad = 0) => {
          this.root.updateMatrixWorld(true);
          const b = new THREE.Box3();
          for (const n of names) if (obj[n]) b.expandByObject(obj[n]);
          return b.isEmpty() ? null : b.expandByScalar(pad);
        };
        const cube = (p: number[], size: number) =>
          new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(...p).applyMatrix4(flange), new THREE.Vector3(size, size, size));
        // (the boxes are padded: the part with some of what it is mounted on, not a close-up)
        if (c.focus === 'pusher') focus = around(PUSHER_PARTS, 30);
        if (c.focus === 'camera') focus = around(['phone'], 40);
        if (c.focus === 'tip' && R.frames.T_tcp) focus = cube(R.frames.T_tcp.world.pos, 130);
        if (c.focus === 'adapter') focus = around(meshes.filter((m) => m.role === 'hardware').map((m) => m.name), 45) ?? cube([0, 0, 0], 150);
        // ... and that part is outlined
        const mark = (names: string[]) => names.forEach((n) => { if (obj[n]) marked.push(obj[n]); });
        if (c.focus === 'pusher') mark(PUSHER_PARTS);
        if (c.focus === 'camera') mark(['phone']);
        if (c.focus === 'adapter') mark(meshes.filter((m) => m.role === 'hardware').map((m) => m.name));
        if (c.focus === 'tip' && obj.tip_tpu) mark(['tip_tpu']);
        else if (c.focus === 'tip' && R.frames.T_tip) {
          // the tip is one body with the rod: an unseen ball just around it gives the outline its shape
          const r = (R.params.rod_D ?? R.params.rod_w ?? R.params.bar_w ?? 15) / 2 + 0.8;
          const ball = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 20), new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false }));
          ball.applyMatrix4(poseMatrix(R.frames.T_tip.world));
          tool.add(ball); marked.push(ball);
        }
      }
      focus ??= loading ? null : boxOf(this.root);   // the whole thing: wait for the arm before framing it
    }

    const accent = new THREE.Color(css('--accent', '#2f5bd3'));
    this.outline.visibleEdgeColor.copy(accent);
    this.outline.hiddenEdgeColor.copy(accent).lerp(new THREE.Color(css('--viewport-bg', '#f0f0ec')), 0.55);   // where something is in front of the part
    this.outline.selectedObjects = marked;

    const key = [c.view, c.carrier?.id ?? '', c.view === 'overall' ? c.adapter?.id ?? '' : '', c.view === 'overall' ? c.focus ?? '' : ''].join('|');

    // Re-frame only when what is looked at changes (view, carrier, adapter, focused part), so dragging a slider keeps
    // the user's camera. Inside the same view the camera travels there and keeps its direction; a new view starts
    // from that view's own direction.
    if (focus && !focus.isEmpty() && key !== this.lastView) {
      const travel = this.fitted && this.lastView !== '' && c.view === this.lastScene;
      this.fit(focus, travel ? undefined : fitDir ?? new THREE.Vector3(1.1, -1.4, 0.8), travel);
      this.lastView = key; this.lastScene = c.view; this.fitted = true;
    }
  }

  /** Frame `box` in the part of the canvas the panels leave free. Without `dir` the camera keeps its direction. */
  private fit(box: THREE.Box3, dir?: THREE.Vector3, travel = false) {
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();
    const w = this.host.clientWidth || 1, h = this.host.clientHeight || 1, i = this.inset;
    const free = Math.max(0.3, Math.min(w - i.l - i.r, h - i.t - i.b) / h);   // the narrower free side, as a share of the height
    const dist = (size / 2) / (Math.tan((this.camera.fov * Math.PI) / 360) * Math.min(1, free)) * 0.95;
    const d = (dir ?? this.camera.position.clone().sub(this.controls.target)).normalize();
    const pos = center.clone().add(d.multiplyScalar(dist));
    const from = this.camera.position.distanceTo(this.controls.target);
    this.camera.near = Math.max(0.5, Math.min(dist, travel ? from : dist) / 200);
    this.camera.far = Math.max(dist, travel ? from : dist) * 50;
    this.camera.updateProjectionMatrix();
    if (travel && !STILL) {
      this.fly = { t0: performance.now(), ms: 550, p0: this.camera.position.clone(), p1: pos, c0: this.controls.target.clone(), c1: center };
    } else {
      this.fly = null;
      this.camera.position.copy(pos);
      this.controls.target.copy(center);
      this.controls.update();
    }
  }

  /** Next update frames the view again from its own direction. */
  resetView() { this.lastView = ''; }
}
