"""Self-contained HTML preview (three.js from a CDN): parts, frames with labels, collision primitives,
real-part reference overlays and the phone camera view."""

import base64
import json

import numpy as np

THREE = 'https://cdn.jsdelivr.net/npm/three@0.160.0'


def _b64(a, dt):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dt).tobytes()).decode()


def mesh_payload(V, F):
    return {'v': _b64(V, '<f4'), 'f': _b64(F, '<u4'), 'nv': int(len(V)), 'nf': int(len(F))}


def write_preview(path, resolved, meshes, refs, title='preview'):
    """resolved: Model.resolved_json(); meshes: part -> (V, F) in root mm; refs: list of (name, V, F)."""
    data = {
        'title': title,
        'frames': {
            n: {
                'parent': f['parent'],
                'module': f['module'],
                'desc': f['desc'],
                'source': f.get('source'),
                'pos': f['world']['pos'],
                'quat': f['world']['quat'],
                'local': f['local'],
            }
            for n, f in resolved['frames'].items()
        },
        'cameras': resolved['cameras'],
        'parts': [
            {
                'name': p['name'],
                'role': p.get('role'),
                'color': p.get('color', '#999999'),
                'mesh': mesh_payload(*meshes[p['name']]) if p['name'] in meshes else None,
                'collision': p['collision'],
            }
            for p in resolved['parts']
        ],
        'refs': [{'name': n, 'mesh': mesh_payload(V, F)} for n, V, F in refs],
        'params': resolved['params'],
    }
    html = HTML.replace('__DATA__', json.dumps(data)).replace('__THREE__', THREE).replace('__TITLE__', title)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f7f9;--panel:#ffffff;--ink:#1d2330;--muted:#677084;--line:#dfe3ea;--accent:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--panel:#1c2027;--ink:#e6e9ef;--muted:#9aa3b2;--line:#2c323c;--accent:#60a5fa}}
*{box-sizing:border-box}body{margin:0;font:13px/1.45 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:var(--bg);color:var(--ink);overflow:hidden}
#app{display:flex;height:100vh}#side{width:330px;min-width:260px;overflow:auto;background:var(--panel);border-right:1px solid var(--line);padding:12px 14px}
#view{flex:1;position:relative}canvas{display:block}
h1{font-size:15px;margin:0 0 8px}h2{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 6px}
label{display:flex;gap:6px;align-items:center;margin:2px 0;cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:11.5px}td{padding:2px 4px;border-bottom:1px solid var(--line);vertical-align:top}
td.n{font-family:ui-monospace,Menlo,monospace;white-space:nowrap}.src{color:var(--muted);font-size:10.5px}
#inset{position:absolute;right:12px;bottom:12px;border:2px solid var(--accent);border-radius:6px;background:#000;overflow:hidden}
#inset .cap{position:absolute;left:6px;top:4px;color:#fff;font-size:11px;text-shadow:0 0 3px #000}
.lbl{font:11px ui-monospace,Menlo,monospace;color:var(--ink);background:color-mix(in srgb,var(--panel) 80%,transparent);padding:0 3px;border-radius:3px;white-space:nowrap}
@media (max-width:700px){#app{flex-direction:column}#side{width:100%;height:40vh}#inset{width:45vw}}
</style>
<script type="importmap">{"imports":{"three":"__THREE__/build/three.module.js","three/addons/":"__THREE__/examples/jsm/"}}</script>
</head><body><div id="app"><div id="side"><h1 id="ttl"></h1>
<h2>Show</h2><div id="toggles"></div>
<h2>Frames (in the root frame, mm)</h2><table id="ftab"></table>
<h2>Parameters</h2><table id="ptab"></table></div>
<div id="view"><div id="inset"><div class="cap">C_main phone camera view</div></div></div></div>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {CSS2DRenderer, CSS2DObject} from 'three/addons/renderers/CSS2DRenderer.js';
const D = __DATA__;
document.getElementById('ttl').textContent = D.title;
const view = document.getElementById('view'), inset = document.getElementById('inset');
const renderer = new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(devicePixelRatio);
view.appendChild(renderer.domElement);
const lr = new CSS2DRenderer(); lr.domElement.style.position='absolute'; lr.domElement.style.top='0'; lr.domElement.style.pointerEvents='none'; view.appendChild(lr.domElement);
const ir = new THREE.WebGLRenderer({antialias:true}); inset.appendChild(ir.domElement);
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const scene = new THREE.Scene(); scene.background = new THREE.Color(dark ? 0x14171c : 0xf6f7f9);
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
const dl = new THREE.DirectionalLight(0xffffff, 1.6); dl.position.set(200, -150, 400); scene.add(dl);
const cam = new THREE.PerspectiveCamera(40, 1, 1, 5000); cam.up.set(0,0,1); cam.position.set(-250, -380, 260);
const ctl = new OrbitControls(cam, renderer.domElement); ctl.target.set(40, -10, 70); ctl.update();
const grid = new THREE.GridHelper(400, 40, 0x888888, dark?0x333a44:0xd5d9e0); grid.rotation.x = Math.PI/2; scene.add(grid);

function dec(b64, T){const s=atob(b64), u=new Uint8Array(s.length); for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i); return new T(u.buffer);}
function geo(m){const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(dec(m.v, Float32Array),3)); g.setIndex(new THREE.BufferAttribute(dec(m.f, Uint32Array),1)); const n=g.toNonIndexed(); n.computeVertexNormals(); return n;}
function q(qq){return new THREE.Quaternion(qq[1],qq[2],qq[3],qq[0]);}

const groups = {};
function group(name){ if(!groups[name]){groups[name]=new THREE.Group(); scene.add(groups[name]);} return groups[name]; }
// parts
for(const p of D.parts){ if(!p.mesh) continue;
  const mat = new THREE.MeshStandardMaterial({color:p.color, metalness:0.05, roughness:0.75, transparent:p.role==='reference', opacity:p.role==='reference'?0.55:1, side:THREE.DoubleSide});
  const m = new THREE.Mesh(geo(p.mesh), mat); group('part:'+p.name).add(m);
  const e = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 25), new THREE.LineBasicMaterial({color:dark?0x0b0d10:0x30343c, transparent:true, opacity:.35})); group('part:'+p.name).add(e);
}
// collision primitives
const cg = group('collision'); cg.visible = false;
const cmat = new THREE.MeshBasicMaterial({color:0xe8743b, wireframe:true});
for(const p of D.parts) for(const c of p.collision){
  let g; if(c.type==='box') g=new THREE.BoxGeometry(...c.size); else if(c.type==='sphere') g=new THREE.SphereGeometry(c.r,20,12);
  else { g=new THREE.CylinderGeometry(c.r,c.r,c.h,24); g.rotateX(Math.PI/2); }
  const m=new THREE.Mesh(g,cmat); m.position.set(...c.pos); m.quaternion.copy(q(c.quat)); cg.add(m); }
// references
for(const r of D.refs){ const m=new THREE.Mesh(geo(r.mesh), new THREE.MeshStandardMaterial({color:0x22c55e, transparent:true, opacity:.28, depthWrite:false, side:THREE.DoubleSide}));
  group('ref:'+r.name).add(m); }
// frames
const fg = group('frames'), lg = group('labels');
const tcp = D.frames['T_tcp'];
for(const [n,f] of Object.entries(D.frames)){
  const big = ['F_robot','T_tcp','C_main','P_phone'].includes(n);
  const a = new THREE.AxesHelper(big?22:14); a.position.set(...f.pos); a.quaternion.copy(q(f.quat)); fg.add(a);
  const d=document.createElement('div'); d.className='lbl'; d.textContent=n; const o=new CSS2DObject(d); o.position.set(...f.pos); lg.add(o);
  if(f.parent){ const pp=D.frames[f.parent].pos; const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...pp), new THREE.Vector3(...f.pos)]), new THREE.LineDashedMaterial({color:0x8b5cf6, dashSize:3, gapSize:2})); l.computeLineDistances(); fg.add(l);}
}
if(tcp){ const s=new THREE.Mesh(new THREE.SphereGeometry(2.5,16,8), new THREE.MeshBasicMaterial({color:0xd946ef})); s.position.set(...tcp.pos); group('frames').add(s); }
// phone camera
const C = D.frames['C_main'], K = D.cameras['C_main'];
const vcam = new THREE.PerspectiveCamera(K.fovy_deg, K.aspect, 1, 3000);
if(C){ vcam.position.set(...C.pos); vcam.quaternion.copy(q(C.quat)); vcam.updateMatrixWorld(); vcam.far=Math.max(60, Math.hypot(C.pos[0]-(tcp?tcp.pos[0]:0), C.pos[1]-(tcp?tcp.pos[1]:0), C.pos[2]-(tcp?tcp.pos[2]:0))*1.05); vcam.updateProjectionMatrix(); const h2=new THREE.CameraHelper(vcam); group('frustum').add(h2); vcam.far=3000; vcam.updateProjectionMatrix(); }

// UI
const tg = document.getElementById('toggles');
function toggle(key, label, on){ const g=groups[key]; if(!g) return; g.visible=on; const l=document.createElement('label'); const c=document.createElement('input'); c.type='checkbox'; c.checked=on; c.onchange=()=>{g.visible=c.checked;}; l.append(c, label); tg.append(l); }
for(const p of D.parts) toggle('part:'+p.name, `${p.name} (${p.role==='reference'?'reference, not printed':'printed'})`, true);
toggle('frames','Frame axes', true); toggle('labels','Frame names', true); toggle('frustum','Camera frustum', true);
toggle('collision','MuJoCo collision primitives', false);
for(const r of D.refs) toggle('ref:'+r.name, `Real-part reference: ${r.name}`, true);
const ft=document.getElementById('ftab');
for(const [n,f] of Object.entries(D.frames)) ft.insertAdjacentHTML('beforeend', `<tr><td class="n">${n}<div class="src">${f.parent??'root'} · ${f.source??''}</div></td><td>${f.pos.map(v=>v.toFixed(2)).join(', ')}<div class="src">${f.desc}</div></td></tr>`);
const pt=document.getElementById('ptab');
for(const [k,v] of Object.entries(D.params)) pt.insertAdjacentHTML('beforeend', `<tr><td class="n">${k}</td><td>${(+v).toFixed(3).replace(/\.?0+$/,'')}</td></tr>`);

function size(){ const w=view.clientWidth, h=view.clientHeight; renderer.setSize(w,h); lr.setSize(w,h); cam.aspect=w/h; cam.updateProjectionMatrix();
  const iw=Math.min(360, w*0.42), ih=iw/K.aspect; ir.setSize(iw, ih); inset.style.width=iw+'px'; inset.style.height=ih+'px'; }
addEventListener('resize', size); size();
window.__ipush={groups, cam, ctl, scene};
(function loop(){ requestAnimationFrame(loop); renderer.render(scene, cam); lr.render(scene, cam);
  const s=[groups.frustum?.visible, groups.labels?.visible]; if(groups.frustum) groups.frustum.visible=false; if(groups.labels) groups.labels.visible=false;
  ir.render(scene, vcam); if(groups.frustum) groups.frustum.visible=s[0]; if(groups.labels) groups.labels.visible=s[1]; })();
</script></body></html>
"""
