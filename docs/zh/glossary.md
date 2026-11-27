# 术语表

中英文文档用同一套术语，两种语言都以这张表为准。

| 英文 | 中文 | 含义 |
| --- | --- | --- |
| pusher | 推杆 | 打印出来的工具：底座、杆、末端，加上手机的支撑结构。 |
| rod | 杆 | 底座和末端之间那段直的圆杆。 |
| tip | 末端 | 和物体接触的部分。默认配置里是一个半球。 |
| TCP (tool centre point) | TCP（工具中心点） | 接触参考点，即坐标系 `T_tcp`，在末端的顶点。 |
| carrier | 载体 | 拿着推杆的东西：机械臂，或者手持握把。 |
| robot flange | 机械臂法兰 | 机械臂上用来装工具的端面，即坐标系 `F_robot`。 |
| mount adapter | 安装转接件 | 载体（机械臂法兰或手腕）和推杆底座之间的零件。 |
| pusher base | 推杆底座 | 推杆底部的那块板，它的安装面是坐标系 `F_mount`。 |
| mounting angle | 安装转角 | 推杆绕法兰轴线转过的角度（`mount_rot`）。 |
| holder | 手机支架 | 把手机固定在推杆上的零件。 |
| config | 配置 | 描述一个工具的 JSON 文件。 |
| parameter | 参数 | 配置里有名字的数值，或者算出数值的表达式。 |
| frame | 坐标系 | 配置的坐标系树里有名字的坐标系。 |
| solved frame | 求解坐标系 | 位姿由求解器根据设计意图算出来的坐标系。 |
| CSG (constructive solid geometry) | CSG（构造实体几何） | 用并集和差集把简单形状组合成实体。 |
| part | 零件 | 工具里的一个实体，绑在某个坐标系上。 |
| print set | 打印组 | 合并成一个 STL 文件的几个打印件。 |
| option | 选项 | 一个开关，控制一组坐标系和零件要不要。 |
| check | 检查 | 对某个坐标系位置的限制。 |
| interference rule | 干涉规则 | 一对不允许重叠的实体。 |
| MJCF | MJCF | MuJoCo 的 XML 模型格式。 |
| mesh | 网格 | 三角面片表面，例如 STL 文件。 |
| add-in | 插件 | `hardware/cad/fusion/` 里那个在 Autodesk Fusion 中运行的程序。 |
| palette | 面板 | 插件在 Fusion 里的窗口，列出全部参数。 |
| episode | episode | 一次录制：机械臂的伺服日志和手机的数据流，放在一个目录里。 |
| leader | leader | 遥操作时操作者手里的设备：一部手机，或者一台 leader 臂。 |
| follower | follower | 跟随 leader 的机械臂。 |
| top camera, wrist camera | 顶部相机、腕部相机 | 固定在工作区上方的手机，和装在工具上的手机。 |
| arm frame | 机械臂坐标系 | 机械臂的底座坐标系：原点在安装面上，X 朝前，Y 朝左，Z 朝上。 |
