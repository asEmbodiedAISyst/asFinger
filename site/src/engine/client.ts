// Main-thread handle on the engine worker. solve() is "latest wins": while one solve runs, only the newest
// request is kept, so dragging a slider never queues up stale work.
import type { SolveResult, ParamValue } from './types';

type Pending = { resolve: (v: any) => void; reject: (e: any) => void };

export class Engine {
  private w: Worker;
  private seq = 0;
  private pending = new Map<number, Pending>();
  private busy = false;
  private queued: { config: any; params: Record<string, ParamValue>; options: Record<string, boolean>; lang: string; resolve: (v: SolveResult | null) => void } | null = null;

  constructor() {
    this.w = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    this.w.onmessage = (e) => {
      const p = this.pending.get(e.data.id);
      if (!p) return;
      this.pending.delete(e.data.id);
      e.data.ok ? p.resolve(e.data.result) : p.reject(new Error(e.data.error));
    };
  }

  private call<T>(msg: any): Promise<T> {
    const id = ++this.seq;
    return new Promise<T>((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.w.postMessage({ id, ...msg }); });
  }

  init(): Promise<{ ms: number }> { return this.call({ type: 'init' }); }

  /** Resolves with the result, or with null if a newer request superseded this one. */
  solve(config: any, params: Record<string, ParamValue>, options: Record<string, boolean> = {}, lang = 'en'): Promise<SolveResult | null> {
    if (this.busy) {
      this.queued?.resolve(null);
      return new Promise((resolve) => { this.queued = { config, params, options, lang, resolve }; });
    }
    this.busy = true;
    return this.call<SolveResult>({ type: 'solve', config, params, options, lang }).finally(() => {
      this.busy = false;
      const q = this.queued; this.queued = null;
      if (q) this.solve(q.config, q.params, q.options, q.lang).then(q.resolve, () => q.resolve(null));
    });
  }

  stl(kind: 'set' | 'part', name: string): Promise<{ file: string; bytes: ArrayBuffer; volume: number; bodies: number }> {
    return this.call({ type: 'stl', kind, name });
  }
}
