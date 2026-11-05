# 项目约定

- 硬件接线的固定记录是 `hardware/引脚分配.md`；代码配置在 `firmware/servo_control/servo_pins.h`。已确认的8路舵机GPIO不再重复向用户询问。
- 舵机PWM接口不等于UART串口；USB COM号会变化，不固定为某个端口。
- CAD、编译及网格检查不替代舵机配合、供电、承重和实机运动测试；不要把命令角度当成传感器反馈。
