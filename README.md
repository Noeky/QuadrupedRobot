# 四足机器人课程设计 · 第 3 组

北京大学 2026–2027 学年秋季学期《先进制造与机器人实践》第 3 组。

八个180°舵机、每腿两自由度。机械文件为试装修订后的 R3。当前固件支持手机 Wi-Fi 面板、串口调角、站姿标定、连续调速、逐腿步态调节、前进/后退/左右转，以及抬后腿打招呼。四拍版前进仍不稳定，新版对角步态待实机对照；转向和倒退是开环差速/反向步态，需要低速、小增益验证。当前继续调稳定前进和直线性，之后再接入传感器。

## 使用入口

- [Arduino 固件与全部指令](firmware/servo_control/README.md)：在 Arduino IDE 中打开同目录的 servo_control.ino，串口115200、New Line。
- [MuJoCo 简化仿真](sim/run_gait.py)：前进/后退/左右转、舵机滞后/死区与录制工具；不替代实机测试。
- [接线与关节编号](hardware/引脚分配.md)：8路舵机PWM引脚的唯一固定记录。
- [SolidWorks 原生装配](cad/current/robot.SLDASM)与[原生零件](cad/current/parts/)：35个组件，装配为定位固定，尚未建立运动配合。
- [整机打印包](releases/QuadrupedRobot_Print_R3.zip)：8种零件、共19件；文件名xN表示总数量。
- [单独的打印 STL](cad/current/print/)、[零件 STEP](cad/current/step/)与[整机 STEP](cad/current/robot.step)。
- [设计与打印说明](docs/设计与打印说明.md)、[五金和工具清单](docs/装配五金清单.md)。
- [机器人相关图片原始压缩包](docs/images/四足机器人相关图片.zip)。
- [几何检查报告](cad/current/validation.json)、[原生重建检查](cad/current/native_validation.tsv)、[整机与打印包一致性报告](cad/current/fit_propagation_check.json)。

![当前装配预览](cad/current/preview.png)

## 目录

```text
cad/current/             当前原生CAD、STEP、打印STL、装配清单和检查报告
firmware/servo_control/  唯一当前固件、手机面板、引脚配置和操作说明
sim/                     MuJoCo简化模型、舵机模型、方向检查与录制工具
hardware/reference/      舵机、原始及实测修订舵臂参考模型
hardware/electronics/    原始原理图与PCB资料
hardware/引脚分配.md      接线与关节编号
releases/                当前整机打印包
docs/                    机械说明、五金清单和原始图片资料
scripts/                 当前建模、几何验证、打包和步态数学检查工具
```

不要单独移动装配文件。复制CAD时保留cad和hardware的目录关系；跨电脑也可在SolidWorks中使用Pack and Go。`.cad_runtime/`仅存放本地运行依赖及可重建缓存，不提交到Git。

## 验证范围

主板固定框孔中心距48.6×39.0mm、厚3mm；HC-SR04可拆支架采用约42×17mm中心距的调节孔。主板从上方已有接口接线，没有额外支撑柱。电池记录为603040、3.7V、800mAh，尚未设计固定结构。工程图工作仍暂停。

CAD实体、闭合网格、静态装配和打印包一致性检查不替代螺钉/线缆避让、配合、承重及实机运动测试。固件没有姿态或关节反馈，显示的角度是命令值。

## 重新生成与检查

本机安装并启动SolidWorks 2026后，使用Windows PowerShell 5.1。其他电脑需在scripts/revise_solidworks.ps1中设置实际SolidWorks API路径。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/revise_solidworks.ps1 -Action Build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/revise_solidworks.ps1 -Action Assembly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/revise_solidworks.ps1 -Action Audit
python -m pip install -r requirements.txt
python scripts/verify_current.py
python scripts/package_current.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/revise_solidworks.ps1 -Action VerifyPropagation
python scripts/check_fit_propagation.py
```

SolidWorks COM API生成原生模型；Python读取STEP进行几何检查和STL派生，不替代原生建模。固件编译和步态数学检查方法见固件说明。
