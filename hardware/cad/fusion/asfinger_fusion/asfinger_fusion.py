"""Build / update a parametric Fusion design from a resolved asFinger model (`asfinger` package).

build():  every CSG leaf becomes  sketch (fully dimensioned) -> extrude/revolve -> Move into place,
          every union/difference becomes a Combine, each part is a component with its own timeline group,
          every frame becomes a Joint Origin (driven by a hidden sketch), params go to the User Parameters table.
update(): changes the existing features in place (sketch dimensions, extrude distances, Move transforms, frame
          sketch points, mesh bodies). Features the user added afterwards (fillets, chamfers, holes...) stay, as long
          as the structure of the CSG tree is unchanged; if it changed, update() reports it and the caller rebuilds.

Everything this module makes is tagged with attributes in the group "ipush" (key = "<part>:<node>"), so nothing
depends on names the user might rename. Joint Origins also carry name/parent/pos/quat, readable with read_frames().
The group name is the earlier name of the project. Existing designs carry it and update() finds its features
through it, so it is kept.
"""

import json
import math
import os
import struct
import tempfile

import adsk.core
import adsk.fusion

CM = 0.1  # asFinger works in mm, the Fusion API in cm
ATTR = 'ipush'  # kept from the earlier project name: existing designs carry this attribute group


# ----------------------------------------------------------------- math helpers
def quat_R(q):
    n = math.sqrt(sum(v * v for v in q)) or 1.0
    w, x, y, z = [v / n for v in q]
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ]


def matrix(pos, quat):
    R = quat_R(quat)
    m = adsk.core.Matrix3D.create()
    V = adsk.core.Vector3D.create
    m.setWithCoordinateSystem(
        adsk.core.Point3D.create(*[v * CM for v in pos]),
        V(R[0][0], R[1][0], R[2][0]),
        V(R[0][1], R[1][1], R[2][1]),
        V(R[0][2], R[1][2], R[2][2]),
    )
    return m


def P3(x, y, z=0.0):
    return adsk.core.Point3D.create(x, y, z)


def param_unit(name):
    n = name.lower()
    if n.endswith(('_angle', '_tilt', '_rot', '_deg')):
        return 'deg'
    if n in ('v_n', 'u_n'):
        return ''
    return 'mm'


def _mm(v):
    return f'{v:.6f} mm'


def tag(entity, key, role):
    entity.attributes.add(ATTR, 'node', key)
    entity.attributes.add(ATTR, 'role', role)


def tagged(design):
    """key -> {role: entity} for everything this module made in this design."""
    out = {}
    for a in design.findAttributes(ATTR, 'node'):
        e = a.parent
        if e is None:
            continue
        r = e.attributes.itemByName(ATTR, 'role')
        out.setdefault(a.value, {})[r.value if r else '?'] = e
    return out


def signature(R):
    """Structure of the model (names and node types, not values): update() works only if this is unchanged."""

    def walk(n):
        return [n['type'], n.get('name'), [walk(c) for c in n.get('children', [])]]

    return json.dumps({'parts': [[p['name'], walk(p['tree'])] for p in R['parts']], 'frames': sorted(R['frames'])})


# ----------------------------------------------------------------- meshes (pure Python, no numpy inside Fusion)
def transformed_stl(src, pos, quat, scale=1.0):
    data = open(src, 'rb').read()
    R = quat_R(quat)

    def tf(v):
        v = [c * scale for c in v]
        return [sum(R[i][j] * v[j] for j in range(3)) + pos[i] for i in range(3)]

    tris = []
    n = struct.unpack('<I', data[80:84])[0] if len(data) >= 84 else 0
    if 84 + 50 * n == len(data):
        for k in range(n):
            vals = struct.unpack('<12f', data[84 + 50 * k : 84 + 50 * k + 48])
            tris.append([tf(vals[3:6]), tf(vals[6:9]), tf(vals[9:12])])
    else:
        vs = [
            list(map(float, l.split()[1:4]))
            for l in data.decode(errors='ignore').splitlines()
            if l.strip().startswith('vertex')
        ]
        tris = [[tf(vs[i]), tf(vs[i + 1]), tf(vs[i + 2])] for i in range(0, len(vs), 3)]
    out = os.path.join(tempfile.gettempdir(), f'asfinger_{os.getpid()}_{abs(hash((src, tuple(pos), tuple(quat))))}.stl')
    with open(out, 'wb') as f:
        f.write(b'asfinger'.ljust(80, b' ') + struct.pack('<I', len(tris)))
        for t in tris:
            f.write(struct.pack('<12fH', 0, 0, 0, *t[0], *t[1], *t[2], 0))
    return out


# ----------------------------------------------------------------- build
class Builder:
    def __init__(self, design, comp, base_dir, log):
        self.d, self.c, self.base_dir, self.log = design, comp, base_dir, log
        self.f = comp.features

    def key(self, n):
        return f'{self.part_name}:{n.get("name") or n["type"]}'

    def _sketch(self, n):
        sk = self.c.sketches.add(self.c.xYConstructionPlane)
        sk.name = f'{n["name"].replace("/", "_")}_sketch'
        sk.isVisible = False
        tag(sk, self.key(n), 'sketch')
        return sk

    def _box_sketch(self, sk, sx, sy):
        L, C, D = sk.sketchCurves.sketchLines, sk.geometricConstraints, sk.sketchDimensions
        a, b = sx / 2 * CM, sy / 2 * CM
        p = [P3(-a, -b), P3(a, -b), P3(a, b), P3(-a, b)]
        l0 = L.addByTwoPoints(p[0], p[1])
        l1 = L.addByTwoPoints(l0.endSketchPoint, p[2])
        l2 = L.addByTwoPoints(l1.endSketchPoint, p[3])
        l3 = L.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)
        C.addHorizontal(l0)
        C.addHorizontal(l2)
        C.addVertical(l1)
        C.addVertical(l3)
        diag = L.addByTwoPoints(l0.startSketchPoint, l1.endSketchPoint)
        diag.isConstruction = True
        C.addMidPoint(sk.originPoint, diag)
        H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        Vt = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        D.addDistanceDimension(l0.startSketchPoint, l0.endSketchPoint, H, P3(0, -b - 0.5))
        D.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, Vt, P3(a + 0.5, 0))

    def _extrude(self, sk, n, dist):
        ei = self.f.extrudeFeatures.createInput(
            sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        ei.setSymmetricExtent(adsk.core.ValueInput.createByString(_mm(dist)), True)
        return self.f.extrudeFeatures.add(ei)

    def _place(self, body, n):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        mf = self.f.moveFeatures
        mi = mf.createInput2(coll)
        mi.defineAsFreeMove(matrix(n['pos'], n['quat']))
        feat = mf.add(mi)
        feat.name = f'{n["name"].replace("/", "_")}_place'
        tag(feat, self.key(n), 'place')
        feat.attributes.add(ATTR, 'pose', json.dumps([n['pos'], n['quat']]))
        return feat.bodies.item(0) if feat.bodies.count else body

    def leaf(self, n):
        t, name = n['type'], n['name'].replace('/', '_')
        if t == 'mesh':
            return self.mesh_leaf(n, name)
        sk = self._sketch(n)
        if t == 'box':
            self._box_sketch(sk, n['size'][0], n['size'][1])
            feat = self._extrude(sk, n, n['size'][2])
        elif t == 'cylinder':
            c = sk.sketchCurves.sketchCircles.addByCenterRadius(sk.originPoint, n['r'] * CM)
            sk.sketchDimensions.addDiameterDimension(c, P3(n['r'] * CM * 1.2, n['r'] * CM * 1.2))
            feat = self._extrude(sk, n, n['h'])
        elif t == 'sphere':
            r = n['r'] * CM
            arc = sk.sketchCurves.sketchArcs.addByCenterStartSweep(sk.originPoint, P3(0, -r), math.pi)
            ln = sk.sketchCurves.sketchLines.addByTwoPoints(arc.startSketchPoint, arc.endSketchPoint)
            sk.geometricConstraints.addCoincident(sk.originPoint, ln)
            sk.geometricConstraints.addVertical(ln)
            sk.sketchDimensions.addRadialDimension(arc, P3(r * 1.2, r * 0.5))
            ri = self.f.revolveFeatures.createInput(
                sk.profiles.item(0), ln, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ri.setAngleExtent(False, adsk.core.ValueInput.createByString('360 deg'))
            feat = self.f.revolveFeatures.add(ri)
        else:
            raise ValueError(t)
        feat.name = name
        tag(feat, self.key(n), 'shape')
        body = feat.bodies.item(0)
        body.name = name
        body = self._place(body, n)
        if n.get('sim') == 'none':
            body.attributes.add(ATTR, 'sim', 'none')
        return body

    def mesh_leaf(self, n, name):
        if not self.whole_part_is_mesh:
            self.log(f'[skip] mesh leaf {name}: a mesh inside a boolean is not supported in Fusion')
            return None
        src = os.path.join(self.base_dir, n['file'])
        if not os.path.exists(src):
            self.log(f'[skip] mesh leaf {name}: file not found {src}')
            return None
        bf = self.f.baseFeatures.add()
        bf.name = f'{name}_mesh'
        tag(bf, self.key(n), 'mesh')
        bf.attributes.add(ATTR, 'pose', json.dumps([n['pos'], n['quat'], n.get('scale', 1.0)]))
        _fill_mesh(self.c, bf, transformed_stl(src, n['pos'], n['quat'], n.get('scale', 1.0)), name)
        return None

    def node(self, n):
        t = n['type']
        if t in ('union', 'difference'):
            bodies = [self.node(ch) for ch in n['children']]
            target, tools = bodies[0], [b for b in bodies[1:] if b is not None]
            if target is None or not tools:
                return target
            coll = adsk.core.ObjectCollection.create()
            for b in tools:
                coll.add(b)
            ci = self.f.combineFeatures.createInput(target, coll)
            ci.operation = (
                adsk.fusion.FeatureOperations.JoinFeatureOperation
                if t == 'union'
                else adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ci.isKeepToolBodies = False
            feat = self.f.combineFeatures.add(ci)
            nm = (n.get('name') or t).replace('/', '_')
            feat.name = f'{nm}_{"union" if t == "union" else "cut"}'
            tag(feat, self.key(n), 'combine')
            return feat.bodies.item(0) if feat.bodies.count else target
        return self.leaf(n)

    def part(self, p):
        self.part_name = p['name']
        tree = p['tree']
        self.whole_part_is_mesh = tree['type'] == 'mesh'
        body = self.node(tree)
        if body is not None:
            body.name = p['name']
        return body


def _fill_mesh(comp, bf, path, name=None):
    # a mesh part holds exactly one base feature; its old mesh is only deletable outside the edit
    for i in range(comp.meshBodies.count - 1, -1, -1):
        comp.meshBodies.item(i).deleteMe()
    bf.startEdit()
    try:
        mb = comp.meshBodies.add(path, adsk.fusion.MeshUnits.MillimeterMeshUnit, bf)
        mb = mb.item(0) if hasattr(mb, 'item') else mb
        if name and mb is not None:
            mb.name = name
    finally:
        bf.finishEdit()


def _timeline_group(design, start, name):
    tl = design.timeline
    end = tl.count - 1
    if end > start:
        try:
            g = tl.timelineGroups.add(start, end)
            g.name = name
        except Exception:
            pass


def _frame_points(fr, axis_len):
    w = fr['world']
    p = [v * CM for v in w['pos']]
    R = quat_R(w['quat'])
    return (p, [p[i] + R[i][0] * axis_len * CM for i in range(3)], [p[i] + R[i][2] * axis_len * CM for i in range(3)])


def _frame_attrs(jo, name, fr):
    a = jo.attributes
    for k, v in (
        ('name', name),
        ('parent', fr.get('parent') or ''),
        ('pos', json.dumps(fr['world']['pos'])),
        ('quat', json.dumps(fr['world']['quat'])),
        ('local', json.dumps(fr.get('local'))),
        ('desc', fr.get('desc', '') or ''),
    ):
        a.add(ATTR, k, v)  # add() overwrites an existing attribute of the same name


def add_frames(design, root, frames, axis_len=10.0, log=print):
    """One hidden sketch with an X and a Z segment per frame, a Joint Origin on each, plus attributes."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'asfinger_frames'
    tag(sk, 'frames', 'sketch')
    lines = sk.sketchCurves.sketchLines
    made = 0
    for name, fr in frames.items():
        o, xe, ze = _frame_points(fr, axis_len)
        lx = lines.addByTwoPoints(P3(*o), P3(*xe))
        lz = lines.addByTwoPoints(lx.startSketchPoint, P3(*ze))
        tag(lx, f'frame:{name}', 'x')
        tag(lz, f'frame:{name}', 'z')
        try:
            ji = root.jointOrigins.createInput(adsk.fusion.JointGeometry.createByPoint(lx.startSketchPoint))
            ji.zAxisEntity = lz
            ji.xAxisEntity = lx
            jo = root.jointOrigins.add(ji)
            jo.name = name
            _frame_attrs(jo, name, fr)
            made += 1
        except Exception as e:
            log(f'[warn] joint origin {name}: {e}')
    sk.isVisible = False
    return made


def add_params(design, params, exprs):
    up = design.userParameters
    for k, v in params.items():
        if not isinstance(v, (int, float)):
            continue
        u = param_unit(k)
        ex = up.itemByName(k)
        if ex:
            ex.expression = f'{v:.10g} {u}'.strip()
        else:
            up.add(
                k,
                adsk.core.ValueInput.createByString(f'{v:.10g} {u}'.strip()),
                u,
                f'asFinger: {exprs[k]}' if k in exprs else 'asFinger',
            )


def clear_design(design):
    """Remove everything a previous export made, so a generated document can be rebuilt."""
    tl = design.timeline
    if tl.count:
        tl.moveToBeginning()
        tl.deleteAllAfterMarker()
    root = design.rootComponent
    for i in range(root.occurrences.count - 1, -1, -1):
        root.occurrences.item(i).deleteMe()
    for i in range(design.userParameters.count - 1, -1, -1):
        try:
            design.userParameters.item(i).deleteMe()
        except Exception:
            pass


def _load(resolved):
    if isinstance(resolved, dict):
        return resolved, resolved.get('base_dir') or '.'
    R = json.load(open(resolved, encoding='utf-8'))
    base = R.get('base_dir')
    if not base or not os.path.isdir(base):  # resolved.json lives in <repo>/out/<name>/
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(resolved))))
        if os.path.isdir(os.path.join(base, 'hardware', 'assets')):  # asset paths are relative to <repo>/hardware
            base = os.path.join(base, 'hardware')
    return R, base


def build(app, resolved, new_document=True, log=print, export_f3d=None, export_step=None, save_to_folder=None):
    """resolved: path to resolved.json or the dict from Model.resolved_json()."""
    R, base_dir = _load(resolved)
    if new_document:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        if save_to_folder is not None:  # save first so later saves (and the MCP harness) have a target
            doc.saveAs(f'asfinger_{R.get("name", "model")}', save_to_folder, 'generated by asfinger_fusion', '')
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    if not new_document:
        clear_design(design)
    root = design.rootComponent
    root.attributes.add(ATTR, 'generated', '1')
    root.attributes.add(ATTR, 'signature', signature(R))
    add_params(design, R['params'], R.get('param_exprs', {}))

    summary = {'parts': {}}
    for p in R['parts']:
        start = design.timeline.count
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        comp = occ.component
        comp.name = p['name']
        body = Builder(design, comp, base_dir, log).part(p)
        summary['parts'][p['name']] = {
            'volume_mm3': body.physicalProperties.volume * 1000 if body else None,
            'bodies': comp.bRepBodies.count,
            'meshes': comp.meshBodies.count,
        }
        _timeline_group(design, start, p['name'])
    start = design.timeline.count
    summary['joint_origins'] = add_frames(design, root, R['frames'], log=log)
    _timeline_group(design, start, 'frames')
    _export(design, summary, export_f3d, export_step)
    return summary


def _export(design, summary, f3d, step):
    em = design.exportManager
    if f3d:
        em.execute(em.createFusionArchiveExportOptions(f3d))
        summary['f3d'] = f3d
    if step:
        em.execute(em.createSTEPExportOptions(step, design.rootComponent))
        summary['step'] = step


# ----------------------------------------------------------------- update in place
def _set(param, expr):
    if param.expression != expr:
        param.expression = expr
        return 1
    return 0


def update(app, resolved, log=print, export_f3d=None, export_step=None):
    """Update an asFinger design in place. Returns a summary; summary['ok'] is False if the structure changed
    (then call build(..., new_document=False) to rebuild)."""
    R, base_dir = _load(resolved)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    old = root.attributes.itemByName(ATTR, 'signature')
    if old is None or old.value != signature(R):
        return {'ok': False, 'reason': 'structure changed (parts, nodes or frames added/removed/renamed)'}
    T = tagged(design)
    add_params(design, R['params'], R.get('param_exprs', {}))
    changed = 0
    missing = []

    def walk(part, n):
        nonlocal changed
        if n['type'] in ('union', 'difference'):
            for c in n['children']:
                walk(part, c)
            return
        key = f'{part}:{n.get("name") or n["type"]}'
        ents = T.get(key, {})
        t = n['type']
        if t == 'mesh':
            bf = ents.get('mesh')
            if bf is None:
                return
            src = os.path.join(base_dir, n['file'])
            prev = bf.attributes.itemByName(ATTR, 'pose')
            pose = json.dumps([n['pos'], n['quat'], n.get('scale', 1.0)])
            if prev is None or prev.value != pose:
                comp = bf.parentComponent
                _fill_mesh(comp, bf, transformed_stl(src, n['pos'], n['quat'], n.get('scale', 1.0)), n.get('name'))
                bf.attributes.add(ATTR, 'pose', pose)
                changed += 1
            return
        sk, shape, place = ents.get('sketch'), ents.get('shape'), ents.get('place')
        if not (sk and shape and place):
            missing.append(key)
            return
        dims = sk.sketchDimensions
        if t == 'box':
            changed += _set(dims.item(0).parameter, _mm(n['size'][0]))
            changed += _set(dims.item(1).parameter, _mm(n['size'][1]))
            changed += _set(shape.extentOne.distance, _mm(n['size'][2]))
        elif t == 'cylinder':
            changed += _set(dims.item(0).parameter, _mm(2 * n['r']))
            changed += _set(shape.extentOne.distance, _mm(n['h']))
        elif t == 'sphere':
            changed += _set(dims.item(0).parameter, _mm(n['r']))
        prev = place.attributes.itemByName(ATTR, 'pose')
        pose = json.dumps([n['pos'], n['quat']])
        if prev is None or prev.value != pose:
            moves.append((place, n, pose))

    moves = []
    for p in R['parts']:
        walk(p['name'], p['tree'])
    # a Move can only be redefined with the timeline rolled back to it: do them in timeline order, then roll forward
    tl = design.timeline
    # (walk order == build order == timeline order, so no sorting needed; indices inside groups are not readable)
    groups = [g for g in tl.timelineGroups if g.isCollapsed] if moves else []
    for g in groups:  # rollTo fails on items inside a collapsed group
        g.isCollapsed = False
    try:
        for place, n, pose in moves:
            place.timelineObject.rollTo(True)
            place.redefineAsFreeMove(matrix(n['pos'], n['quat']))
            place.attributes.add(ATTR, 'pose', pose)
            changed += 1
    finally:
        tl.moveToEnd()
        for g in groups:
            g.isCollapsed = True

    # frames: move the sketch points the joint origins sit on
    jos = {jo.name: jo for jo in root.jointOrigins}
    for name, fr in R['frames'].items():
        ents = T.get(f'frame:{name}', {})
        lx, lz = ents.get('x'), ents.get('z')
        if not (lx and lz):
            missing.append(f'frame:{name}')
            continue
        o, xe, ze = _frame_points(fr, 10.0)
        moved = 0
        for sp, tgt in ((lx.startSketchPoint, o), (lx.endSketchPoint, xe), (lz.endSketchPoint, ze)):
            g = sp.geometry
            d = [tgt[0] - g.x, tgt[1] - g.y, tgt[2] - g.z]
            if max(abs(v) for v in d) > 1e-9:
                sp.move(adsk.core.Vector3D.create(*d))
                moved = 1
        changed += moved
        if name in jos:
            _frame_attrs(jos[name], name, fr)
    design.computeAll()  # joint origins report stale transforms until the design is recomputed
    summary = {'ok': True, 'changed': changed, 'missing': missing}
    _export(design, summary, export_f3d, export_step)
    return summary


def read_frames(design):
    """Read the frames back from the Joint Origins' attributes (for a round trip to JSON)."""
    out = {}
    for jo in design.rootComponent.jointOrigins:
        a = jo.attributes
        if a.itemByName(ATTR, 'name'):
            out[a.itemByName(ATTR, 'name').value] = {
                'parent': a.itemByName(ATTR, 'parent').value or None,
                'pos': json.loads(a.itemByName(ATTR, 'pos').value),
                'quat': json.loads(a.itemByName(ATTR, 'quat').value),
            }
    return out
