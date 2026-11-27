# Glossary

The English and the Chinese pages use the same terms. This table is the reference for both languages.

| English | Chinese | Meaning |
| --- | --- | --- |
| pusher | 推杆 | The printed tool: base, rod, tip and the support of the phone. |
| rod | 杆 | The straight round bar between the base and the tip. |
| tip | 末端 | The part that touches the object. In the default config it is a hemisphere. |
| TCP (tool centre point) | TCP（工具中心点） | The contact reference point. It is the frame `T_tcp`, at the apex of the tip. |
| carrier | 载体 | What holds the pusher: a robot arm or a hand grip. |
| robot flange | 机械臂法兰 | The face of the robot that a tool is bolted to. It is the frame `F_robot`. |
| mount adapter | 安装转接件 | A part between the carrier (a robot flange or a wrist) and the pusher base. |
| pusher base | 推杆底座 | The plate at the bottom of the pusher. Its mounting face is the frame `F_mount`. |
| mounting angle | 安装转角 | The turn of the pusher about the flange axis (`mount_rot`). |
| holder | 手机支架 | The part that carries the phone on the pusher. |
| config | 配置 | The JSON file that describes one tool. |
| parameter | 参数 | A named number in the config, or an expression that gives a number. |
| frame | 坐标系 | A named coordinate frame in the frame tree of the config. |
| solved frame | 求解坐标系 | A frame whose pose is computed by a solver from a design intent. |
| CSG (constructive solid geometry) | CSG（构造实体几何） | Solids built from simple shapes with union and difference. |
| part | 零件 | One solid of the tool, bound to a frame. |
| print set | 打印组 | Several printed parts fused into one STL file. |
| option | 选项 | A switch that turns a group of frames and parts on or off. |
| check | 检查 | A limit on the position of a frame. |
| interference rule | 干涉规则 | A pair of solids that must not overlap. |
| MJCF | MJCF | The XML model format of MuJoCo. |
| mesh | 网格 | A triangle surface, for example an STL file. |
| add-in | 插件 | The program in `hardware/cad/fusion/` that runs inside Autodesk Fusion. |
| palette | 面板 | The window of the add-in in Fusion that lists the parameters. |
| episode | episode | One recording: the servo log of the arm and the streams of the phones, in one folder. |
| leader | leader | The device in the hand of the operator in teleoperation: a phone or a leader arm. |
| follower | follower | The arm that follows the leader. |
| top camera, wrist camera | 顶部相机、腕部相机 | The fixed phone above the workspace, and the phone on the tool. |
| arm frame | 机械臂坐标系 | The base frame of the arm: origin on the mounting surface, X forward, Y left, Z up. |
