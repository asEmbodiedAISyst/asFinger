export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number]; // [w, x, y, z], MuJoCo order

export interface Pose { pos: Vec3; quat: Quat }

export interface RNode {
  type?: 'union' | 'difference' | 'box' | 'sphere' | 'cylinder' | 'mesh';
  ref?: string;          // interference rules: a whole part, by name
  name?: string;
  children?: RNode[];
  size?: Vec3;
  r?: number;
  h?: number;
  file?: string;
  scale?: number;
  pos?: Vec3;
  quat?: Quat;
  sim?: string;
}

export interface ResolvedFrame { parent: string | null; desc?: string; module?: string; world: Pose; local: Pose; source?: string }

export interface ResolvedPart {
  name: string; frame: string; role?: string; color?: string; density?: number; desc?: string; tree: RNode;
}

export interface Resolved {
  name: string;
  params: Record<string, number>;
  param_exprs: Record<string, string>;
  frames: Record<string, ResolvedFrame>;
  cameras: Record<string, { fovy_deg: number; aspect: number; resolution: [number, number] }>;
  parts: ResolvedPart[];
  /** interference rules that apply (src/asfinger/interference.py): both sides as resolved trees */
  interference?: { id: string; a: RNode; b: RNode; tol: number; msg: string; msg_en?: string | null; level?: 'error' | 'warn' }[];
  options?: Record<string, boolean>;
}

export interface PartMesh {
  name: string; role?: string; color?: string; frame: string;
  positions: Float32Array; indices: Uint32Array; volume: number;
}

export interface SolveResult {
  resolved: Resolved;
  checks: string[];
  /** notes that do not block the export (interference rules with level "warn", e.g. a screw that needs a short key) */
  warnings: string[];
  config: any;          // the config with edited params and re-solved results, ready to save
  meshes: PartMesh[];
  /** where solids overlap that must not (shown in red, notes in amber); their messages are in `checks` / `warnings` */
  overlaps: { id: string; positions: Float32Array; indices: Uint32Array; volume: number; level: 'error' | 'warn' }[];
  ms: { python: number; geometry: number };
}

export type ParamValue = number | string;
