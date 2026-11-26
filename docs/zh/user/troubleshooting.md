# 排错

每一条先给出提示信息或现象，再说原因和处理办法。

## 命令行

**`[warn] P_phone: saved result is stale (inputs changed); run with --resolve to update`**

改了手机求解器用到的参数，但生成时用的还是存着的旧位姿。在命令里加上 `--resolve`。见[坐标系](frames.md#求解坐标系)。

**改参数之后出现 `[check] ...`**

有检查没通过。提示里写着坐标系、它的坐标和允许的范围。默认配置里最常见的原因是：杆缩短之后手机位置太低。调大 `phone_flange_angle` 或 `distance`。

**`[interference] ... (phone_vs_body: 8632.7 mm³)`**

两个实体重叠了。冒号前面是规则名，后面的数字是重叠体积。提示里会说该改哪个参数。规则表见[检查与干涉规则](checks.md#默认配置里的规则)。

**干涉提示是中文，我需要英文**

命令行打印的是每条规则的默认提示。可以看提示里的规则名，或者在 Python 里调用 `m.interference(lang='en')`。

**`KeyError: 'unknown parameter ...'` 或 `KeyError: 'unknown option ...'`**

`--set` 和 `--option` 只接受配置里已有的名字。用下面的命令列出全部参数：`python -c "from asfinger import Model; print(list(Model.load('CONFIG').cfg['params']))"`。

**`ExprError: unknown name ...` 或 `unsupported syntax ...`**

表达式里用了不是参数的名字，或者用了不允许的语法。允许的语法见[配置文件](config-file.md#参数与表达式)。

**`ValueError: ... is not a closed (manifold) solid`**

导入的网格有破洞或开放的边。用网格工具修好之后重新导出。

**`FileNotFoundError`，找不到 `assets/` 里的文件**

配置是到“自己所在目录的旁边”去找 `assets/`，不是到当前目录去找。把配置放到和 `assets/` 相邻的目录里，或者在 `file` 里写绝对路径。

**`frame cycle at ...` 或 `frame X refers to unknown frame Y`**

坐标系树里有环，或者某个坐标系引用的父坐标系、目标坐标系不存在。

**`Fusion add-in not reachable on port 47910`**

`asfinger send` 是把配置发给 Autodesk Fusion 里的插件，而这个端口上没有程序在监听。先启动 Fusion 并运行插件。如果插件已经在运行，那就是它启动时端口被别的程序占着，插件的面板上会有提示。见 [Fusion 插件](fusion.md#限制)。

## 输出

**`report.json` 里某个打印组的 `"bodies"` 是 2 或更大**

打印组里的零件没有连在一起，打印出来会是分开的几块。检查决定手机支架位置的那些参数。

**`preview.html` 是空白的**

页面要联网加载 three.js，还要求配置里有名为 `C_main` 的相机。配置里没有这个相机，或者生成时加了 `--option phone=0`，页面就是空白的。这时用网页编辑器或者网格查看软件看 STL。

**打印出来的推杆和手机壳对不上**

`back_to_mount` 是手机壳背面的厚度。量一下自己的手机壳，改这个参数。见[坐标系](frames.md#手机坐标系的已知局限)。

## 网页编辑器

**“编辑器需要较宽的桌面浏览器窗口（≥ 1100 px）。”**

把窗口拉宽，或者换台式机 / 笔记本电脑。

**一直停在“正在加载几何引擎”**

第一次打开要下载约 13 MB。如果一直不消失，检查网络后刷新页面。

**导出 STL 的按钮是灰的**

有检查或干涉规则没通过。看提示信息，改它提到的参数，再导出。导出配置的按钮一直可用。

**我的参数不见了**

编辑器把参数存在某一个浏览器的 local storage 里。换浏览器、用无痕窗口或者清除了网站数据，都会从默认值开始。想保留工作成果，请导出配置。
