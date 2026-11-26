# 检查与干涉规则

配置里可以写两类测试。检查（check）限制某个坐标系的位置；干涉规则（interference rule）找出互相重叠的实体。这一页说明两者的写法，并列出它们发现不了的问题。

## 检查

检查拿某个坐标系在根坐标系里的一个坐标，和下限或上限比较。

```json
"checks": [
  {"frame": "J_foot", "axis": "z", "min": "plate_t",
   "msg": "手机太低，支撑条会穿到法兰面以下", "msg_en": "Phone too low: the spine would pass below the flange face."}
]
```

`axis` 是 `x`、`y` 或 `z`（默认 `z`）。`min` 和 `max` 是表达式。`msg` 是默认的提示信息，`msg_en` 是英文提示。

`asfinger build` 和 `asfinger frames` 把没通过的检查逐条打印出来，每行以 `[check]` 开头。在 Python 里，`m.check()` 返回提示信息，`m.check(lang='en')` 返回英文的。

## 干涉规则

一条规则有 `a`、`b` 两方。两方重叠的体积超过 `tol_mm3`（默认 1 mm³）时，规则不通过。

```json
"interference": [
  {"id": "phone_vs_body", "a": "phone", "b": "tool_body", "msg": "...", "msg_en": "..."},
  {"id": "holder_vs_rod", "a": "holder", "b": {"part": "tool_body", "only": ["rod", "tip"]}},
  {"id": "sight_to_tip",
   "a": {"sight": {"from": "C_main", "to": "T_tip", "stop_before": "rod_D/2 + 1", "r": 0.5}},
   "b": [{"part": "tool_body", "only": ["adapter", "beam_mitred", "spine_mitred"]}, "holder", "phone"],
   "tol_mm3": 0.3}
]
```

每一方可以是：

| 写法 | 含义 |
| --- | --- |
| `"phone"` | 整个零件。 |
| `{"part": "tool_body", "only": [名字]}` | 零件里指定的几个节点。 |
| `{"part": "tool_body", "skip": [名字]}` | 零件里去掉指定节点后剩下的部分。 |
| `{"sight": {"from": F, "to": F, "r": r, "stop_before": d}}` | 两个坐标系原点之间的一根细圆柱，代表视线。 |
| `{"csg": 节点, "frame": F}` | 只为测试而画的实体，例如螺钉头，或者给工具留的空间。 |
| 上面几种组成的列表 | 它们的并集。 |

规则还可以带：

- `enabled`：表达式，值为 0 时跳过这条规则。
- `level`：`"error"`（默认）或 `"warn"`。error 表示做不出来；warn 只是不方便，例如某个螺钉要用短的内六角扳手。

规则涉及的零件或坐标系被选项关掉时，这条规则跳过。

`asfinger build` 把 error 打印成 `[interference]` 行，把 warn 打印成 `[warning]` 行，两者都写进 `report.json`。在 Python 里，`m.interference()` 返回 error，`m.interference(level='warn')` 返回 warn。网页编辑器计算同样的规则，把重叠部分标成红色；只要有 error，就不能导出 STL。

> **提示信息的语言。** 命令行打印的是 `msg`。本仓库的配置里，`msg` 是中文，`msg_en` 是英文。需要英文提示时，在 Python 里用 `m.check(lang='en')` 和 `m.interference(lang='en')`。

## 默认配置里的规则

| 规则 | 级别 | 什么时候不通过 |
| --- | --- | --- |
| `phone_vs_body` | error | 推杆穿过了手机。 |
| `phone_vs_holder` | error | 手机和支架重叠（`back_to_mount` 太小）。 |
| `holder_vs_rod` | error | 杆穿过了支架。 |
| `sight_to_tip` | error | 主摄到末端的视线被实体挡住。 |
| `adapter_vs_body` | error | 推杆和法兰转接件重叠。 |
| `screw_heads` | error | 底座上的螺钉头碰到推杆（只在 `mount_screws = 2` 时检查）。 |
| `screw_access` | error | 螺钉上方放不下内六角扳手（只在 `mount_screws = 2` 时检查）。 |
| `screw_driver` | warn | 直螺丝刀够不到某个螺钉（只在 `mount_screws = 2` 时检查）。 |

唯一的一条检查针对 `J_foot`：手机位置太低、支撑结构会伸到法兰面以下时不通过。

## 这些测试发现不了什么

- **只测规则里列出的组合。** 没有写进任何规则的两个实体，重叠了也不会有提示。
- **很小的重叠算通过。** 重叠体积小于 `tol_mm3` 时不报告。两个面只是贴在一起，重叠体积为零。
- **不测间隙。** 规则只报告重叠。间隙太小、装不进去或者没留打印公差，都不会报告。
- **视线只是一根细线。** `sight_to_tip` 测的是从 `C_main` 到末端、半径 0.5 mm 的一根圆柱，不是整个视场，也不管别的相机。
- **模型里没有机械臂。** 没有规则去测推杆或手机会不会碰到机械臂的连杆或桌面。
- **不测能不能打印。** 悬垂、壁厚、强度都不在检查范围内。手机支架的卡扣用哑光 PLA 打印很脆，建议改用 PETG，或者把卡扣单独平放打印。
- **求解结果过期时，测试结果不可信。** 测试用的是存着的手机位姿，见[坐标系](frames.md#求解坐标系)。
- **手机只是一个盒子。** 零件 `phone` 是替身：一个外形尺寸和 iPhone 17 Pro 相同的长方体，加一个代表主摄的圆环。没有手机壳，也没有完整的相机凸台。
