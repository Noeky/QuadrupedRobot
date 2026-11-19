# 项目约定

- 硬件接线的固定记录是 `hardware/引脚分配.md`；代码配置在 `firmware/servo_control/servo_pins.h`。已确认的8路舵机GPIO不再重复向用户询问。
- 舵机PWM接口不等于UART串口；USB COM号会变化，不固定为某个端口。
- CAD、编译及网格检查不替代舵机配合、供电、承重和实机运动测试；不要把命令角度当成传感器反馈。
- 调试或修改机器人参数前，先让用户发 `ws` 并把全文保存到 `firmware/servo_control/calibration_backup.md`；没有备份不要执行 `walk save` 或 `stand save`，也不要建议勾选 Erase All Flash。`walk set`/`walk speed`/`walk deadband` 只改 RAM，可安全试。
