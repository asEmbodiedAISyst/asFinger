# 替用户使用 asFinger

这一页写给替人生成或修改工具配置的 agent。

## 安装

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
```

- 需要 Python 3.10 或更高版本。
- 导入名是小写的 `asfinger`，命令是 `asfinger`。
- 配置在 `hardware/configs/`，配置引用的网格在 `hardware/assets/`。

## 入口

| 入口 | 作用 |
| --- | --- |
| `asfinger build CONFIG -o OUT` | 把 STL、MJCF、预览、`resolved.json` 和 `report.json` 写到 `OUT`。 |
| `asfinger frames CONFIG` | 打印每个坐标系的位姿。 |
| `--set NAME=VALUE` | 在这一次运行里改一个参数。要改多个参数就重复这个选项。 |
| `--option NAME=0` 或 `NAME=1` | 在这一次运行里开关一个选项。 |
| `--resolve` | 重新运行求解器。不带 `--set` 和 `--option` 时，还会改写配置文件。 |
| `from asfinger import Model` | Python 接口。 |

## 常用调用

生成默认工具：

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/default
```

生成一个变体，不改配置文件：

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/variant --resolve --set rod_L=160 --set rod_tilt=25
```

在 Python 里取 TCP 位姿和测试结果：

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json').set(rod_L=160)
R = m.resolve(resolve=True)  # solve again after a parameter change
tcp = m.root_to('T_tcp', R)  # pose in the root frame F_robot
print(tcp.p, tcp.quat())  # mm, [w, x, y, z]
print(m.check(R, lang='en'))  # [] = no failed check
print(m.interference(R, lang='en'))  # [] = no overlap
m.build('out/rod_160', resolve=True)
```

把改过的配置存成新文件：

```python
m.cfg['name'] = 'my_variant'
m.save('hardware/configs/my_variant.json')
```

## 输入与输出

- 输入：一份 JSON 配置。格式见[配置文件](../user/config-file.md)和[坐标系](../user/frames.md)。
- 单位：毫米、度、g/cm³。MJCF 文件用米。四元数是 `[w, x, y, z]`。
- `Model.frames()` 返回 `(world, local, info)`。`world[name]` 是一个位姿，有 `.p`（位置）、`.R`（3×3 矩阵）和 `.quat()`。
- `Model.build(out_dir)` 返回 `(resolved, report)`，并写出[快速上手](../user/quickstart.md#输出文件)里列出的文件。
- `Model.check()` 和 `Model.interference()` 返回字符串列表。空列表表示没有测试不通过。
- 异常：参数名或选项名不存在时是 `KeyError`；表达式有误时是 `asfinger.expr.ExprError`；坐标系树有误，或者网格不是封闭实体时是 `ValueError`；网格文件不存在时是 `FileNotFoundError`。

## 规则

- 改了参数之后，命令行加 `--resolve`，Python 里传 `resolve=True`。不这样做，手机位姿是过期的，检查结果无效。
- 告诉用户某个变体可以打印之前，先确认 `check()` 和 `interference()` 都返回空列表，并且 `report.json` 里每个打印组的 `"bodies"` 都是 1。
- 测试不通过时，把提示信息和规则名告诉用户。不要为了让它通过而调大 `tol_mm3` 或删掉规则。
- 不要对 `hardware/configs/` 里的配置运行不带 `--set` 的 `asfinger build ... --resolve`，除非用户要求更新那个文件。这条命令会改写文件。
- 变体写到新文件里。不要覆盖 `iphone17pro_default.json` 和 `rebot_rs_flange.json`。
- 配置要放在旁边有 `assets/` 的目录里。配置里的网格路径相对于配置所在目录的上一级。
- 把 `resolved.json` 发给别人之前，删掉 `base_dir` 字段，里面是本机路径。
- 不要用 `asfinger send`。它需要一个不在本仓库里的 CAD 插件。
- 把和用户的请求有关的局限告诉用户，这些局限列在[检查与干涉规则](../user/checks.md#这些测试发现不了什么)和[坐标系](../user/frames.md#手机坐标系的已知局限)两页里。`back_to_mount` 必须和用户的手机壳相符。
- 用户没有 Python 环境时，让他们用[网页编辑器](https://asembodiedaisyst.github.io/asFinger/zh/editor/)。
