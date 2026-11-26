# 四足机器人课程设计 · 第 3 组

北京大学 2026–2027 学年秋季学期《先进制造与机器人实践》第 3 组。

第 13 周已完成 R3 四足样机的打印装配、八路舵机标定和地面试走。对角步态先在 MuJoCo 中设计，再按实机四条腿的落脚情况逐腿调参。课程录像记录了沿标线前进、前后换向、转向回正和原地抬腿。手机 Wi-Fi 面板和 USB 串口共用 ESP32 命令处理器。

第 13 周基础版（`5eb502e`）按人工指令行走。用该版本的 `python sim/compare_firmware.py` 可复现报告中的六组数据：两组均从 1.50 s 计至 13.50 s，前进基准为 183.8 mm，实机参数的固件回放为 149.3 mm。当前主分支还包含 HC-SR04 测距和可选自动避障，Trig 接 GPIO33，Echo 接 GPIO27。

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

CAD 检查记录零件和静态装配的几何结果。样机已完成自重下的地面运动，实机录像未同步测量行走距离和航向。固件没有姿态或关节反馈，显示的角度是命令值。

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
