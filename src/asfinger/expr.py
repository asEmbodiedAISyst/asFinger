"""Safe evaluation of the small expressions allowed in configs, e.g. "rod_L - tip_R" or "pcd/2*cosd(45)".

Allowed: numbers, parameter names, + - * / // % **, unary +/-, parentheses, ternary `a if c else b`,
comparisons, and the functions in FUNCS. Angles in the *d functions are degrees.
The same grammar is implemented in the web viewer, so a config evaluates identically in both.
"""

import ast
import math

FUNCS = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'atan2': math.atan2,
    'sqrt': math.sqrt,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'radians': math.radians,
    'degrees': math.degrees,
    'sind': lambda d: math.sin(math.radians(d)),
    'cosd': lambda d: math.cos(math.radians(d)),
    'tand': lambda d: math.tan(math.radians(d)),
    'asind': lambda x: math.degrees(math.asin(x)),
    'acosd': lambda x: math.degrees(math.acos(x)),
    'atand': lambda x: math.degrees(math.atan(x)),
    'atan2d': lambda y, x: math.degrees(math.atan2(y, x)),
}
CONSTS = {'pi': math.pi, 'true': 1, 'false': 0}

_BIN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}
_CMP = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


class ExprError(ValueError):
    pass


def evaluate(src, params):
    """Evaluate a number, a bool, or an expression string against `params` (dict name -> number)."""
    if isinstance(src, bool):
        return 1.0 if src else 0.0
    if isinstance(src, (int, float)):
        return float(src)
    if not isinstance(src, str):
        raise ExprError(f'not a number or expression: {src!r}')
    try:
        tree = ast.parse(src, mode='eval')
    except SyntaxError as e:
        raise ExprError(f'bad expression {src!r}: {e}') from None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in params:
                return evaluate(params[n.id], params)
            if n.id in CONSTS:
                return float(CONSTS[n.id])
            raise ExprError(f'unknown name {n.id!r} in {src!r}')
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _CMP:
            return 1.0 if _CMP[type(n.ops[0])](ev(n.left), ev(n.comparators[0])) else 0.0
        if isinstance(n, ast.IfExp):
            return ev(n.body) if ev(n.test) else ev(n.orelse)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
            return float(FUNCS[n.func.id](*[ev(a) for a in n.args]))
        raise ExprError(f'unsupported syntax in {src!r}')

    return ev(tree)


def ev_vec(v, params, n=3):
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise ExprError(f'expected a list of {n} values, got {v!r}')
    return [evaluate(x, params) for x in v]


def resolve_params(params):
    """Return a dict with every parameter evaluated to a float (parameters may reference each other)."""
    return {k: evaluate(v, params) for k, v in params.items()}
