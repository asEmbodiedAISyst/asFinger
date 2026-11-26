"""Small rigid-transform library in pure Python (no numpy), so the same code runs inside Fusion.

Conventions
  * vectors are lists [x, y, z]; rotations are 3x3 row-major lists; quaternions are [w, x, y, z]
  * Tf(R, p) maps child coordinates to parent coordinates: x_parent = R @ x_child + p
"""

import math

I3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def add(a, b):
    return [a[i] + b[i] for i in range(3)]


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def mul(a, s):
    return [a[i] * s for i in range(3)]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n < 1e-12:
        raise ValueError('zero-length vector')
    return [x / n for x in a]


def mm(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(A, v):
    return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]


def tr(A):
    return [[A[j][i] for j in range(3)] for i in range(3)]


def cols(a, b, c):
    return [[a[0], b[0], c[0]], [a[1], b[1], c[1]], [a[2], b[2], c[2]]]


def col(A, j):
    return [A[0][j], A[1][j], A[2][j]]


def axang(axis, deg):
    k = unit(axis)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    C = 1 - c
    x, y, z = k
    return [
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ]


def from_xyaxes(xa, ya):
    x = unit(xa)
    y = sub(ya, mul(x, dot(x, ya)))
    y = unit(y)
    z = cross(x, y)
    return cols(x, y, z)


def quat_to_R(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def R_to_quat(R):
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (R[2][1] - R[1][2]) / s
        y = (R[0][2] - R[2][0]) / s
        z = (R[1][0] - R[0][1]) / s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        w = (R[2][1] - R[1][2]) / s
        x = 0.25 * s
        y = (R[0][1] + R[1][0]) / s
        z = (R[0][2] + R[2][0]) / s
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        w = (R[0][2] - R[2][0]) / s
        x = (R[0][1] + R[1][0]) / s
        y = 0.25 * s
        z = (R[1][2] + R[2][1]) / s
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
        w = (R[1][0] - R[0][1]) / s
        x = (R[0][2] + R[2][0]) / s
        y = (R[1][2] + R[2][1]) / s
        z = 0.25 * s
    q = [w, x, y, z]
    if w < 0:
        q = [-c for c in q]
    return q


class Tf:
    __slots__ = ('R', 'p')

    def __init__(self, R=None, p=None):
        self.R = [r[:] for r in (R or I3)]
        self.p = list(p or [0.0, 0.0, 0.0])

    def __mul__(self, o):
        return Tf(mm(self.R, o.R), add(mv(self.R, o.p), self.p))

    def inv(self):
        Rt = tr(self.R)
        return Tf(Rt, mul(mv(Rt, self.p), -1))

    def pt(self, v):
        return add(mv(self.R, v), self.p)

    def vec(self, v):
        return mv(self.R, v)

    def quat(self):
        return R_to_quat(self.R)

    def mat4(self):
        R, p = self.R, self.p
        return [R[0] + [p[0]], R[1] + [p[1]], R[2] + [p[2]], [0.0, 0.0, 0.0, 1.0]]

    def to_json(self, nd=6, qd=8):
        return {'pos': [round(v, nd) for v in self.p], 'quat': [round(v, qd) for v in self.quat()]}

    @staticmethod
    def from_json(d):
        return Tf(quat_to_R(d['quat']), d['pos'])

    def __repr__(self):
        return f'Tf(p={[round(v, 3) for v in self.p]}, q={[round(v, 4) for v in self.quat()]})'
