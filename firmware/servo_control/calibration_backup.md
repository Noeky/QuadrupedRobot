# 板内参数备份

> 规则：任何 `walk save`、`stand save` 或重刷固件之前，先运行 `ws`，把全文粘贴到下面的“当前备份”。
> 正常 Arduino 上传不会清 NVS；Tools → **Erase All Flash Before Sketch Upload** 必须保持 Disabled。
> `walk set`、`walk speed`、`walk deadband` 只改 RAM，断电/重启后恢复板内保存值，可安全试。

## 兼容性说明

2026-11-19 加入前进/后退/左右转时，没有修改 `profile-v2`（站姿/方向）或 `legs-v2`（四腿步态）的二进制结构；正常 Arduino 上传会保留板内现有标定和步态。`walk turn` 的差速增益是 RAM-only，不属于存档。用本文件的当前 stand/dir/LegTuning 计算，前进/后退/左右转的命令角范围约 65～111°，均在 0～180° 内，不需要为转向重新标定。新固件 `ws` 会多一行 `motion=...`，原有 stand/dir/leg 行不变。

`foot offset MM` 也是 RAM-only；它同时平移 `stand` 目标与步态足端轨迹，负值=足端后移。若要把偏移固化，先 `foot offset X`、`stand`，再 `stand record`（记录时自动把 offset 归零）和 `stand save`，这会覆盖 `quad-walk` 的站姿/方向；`legs-v2` 不变，不需要 `walk save`。

`wave` / `wave leg 1|2|3|4` 同样 RAM-only；默认左前腿 20mm（髋角约30°），后腿 25mm；前腿 wave 的支撑脚前移8mm，FR/RL +6mm、RR -4mm，使重心相对右后；支撑腿还使用当前步态 depth 和 foot offset，不改任何存档。前腿抬起会有俯仰，需托住实测。

`walk center MM` 只平移步态足端前后中心，不移动 stand；它由 `walk save` 写入 `quad-gait` 的新键 `center`。旧步态存档没有该键时按 0 读取；`walk reset` 把它归 0。原 `legs-v2` 结构不变。

`avoid` 的阈值、方向、时长、stride、max 都是 RAM-only，不写存档；`avoid on/off` 也只影响当前运行。`turn left/right` 的时长同样只用于本次/避障后续，默认 2s 需按实机 90° 标定。

`walk bias X` 是直行偏置（正=左），只作用于 turn 目标为 0 的直行；由 `walk save` 写入 `quad-gait` 的新键 `bias`，旧存档按 0 读取；`walk reset` 归 0。你验证过的 0.09 可以直接作为 `bias` 保存，`walk turn` 可恢复为 0.5 用于真正的左右转。

## 参数存放位置

| 内容 | NVS 命名空间 | 写入命令 | 读取/恢复 |
|---|---|---|---|
| 站姿角、8 路方向 | `quad-walk` | `stand save` | 开机自动读；`stand load` |
| 四腿 lift/depth/stride/lift%/lower% | `quad-gait` | `walk save` | 开机自动读；`walk load` |
| Wi-Fi 配置 | `quad-net` | 手机页面保存 | 开机自动读 |

`speed` 和 `deadband` 只存在 RAM，重启回到 1.0 和 1。

## 当前备份

备份时间：2026-11-21 21:57:39（状态头、1 路）；stand 2–8 和四腿来自 21:50:13，1 路两次都是 85；如中间改过请重发完整 `ws`。

```text
walking=0 standCaptured=1 ready=1 speed=1.00 deadband=1.00 deg nominal support=65mm
motion=stopped dir=1.00 turn=0.00 gain=0.50 targetDir=1.00 targetTurn=0.00 footOffset=0.0 mm walkCenter=-8.0 mm walkBias=0.000 waving=0 waveLeg=1
1 stand=85 dir=-1
2 stand=80 dir=1
3 stand=95 dir=1
4 stand=100 dir=-1
5 stand=90 dir=-1
6 stand=80 dir=1
7 stand=100 dir=1
8 stand=75 dir=-1
leg 1 lift=8.000 depth=2.000 stride=24.000 lift%=25.00 lower%=25.00
leg 2 lift=10.000 depth=0.000 stride=26.000 lift%=25.00 lower%=25.00
leg 3 lift=10.000 depth=-1.000 stride=24.000 lift%=25.00 lower%=25.00
leg 4 lift=10.000 depth=2.000 stride=24.000 lift%=25.00 lower%=25.00
```

已确认：

- 这是你**把机身调平后**的新站姿/步态；方向模式仍是 `-1,+1,+1,-1,-1,+1,+1,-1`。
- 前腿抬脚已降到 8/10mm，步长 24/26mm；四腿 depth 分别为 +2/0/-1/+2mm。
- 补发完整 `ws` 后要替换上面两行“缺”标记，并确认新站姿是否已经 `stand save`。

## 历史备份（2026-11-19，旧前倾站姿）

仅作回滚参考，不建议再直接套用：

```text
walking=0 standCaptured=1 ready=1 speed=1.00 deadband=1.00 deg nominal support=65mm
1 stand=70 dir=-1
2 stand=90 dir=1
3 stand=110 dir=1
4 stand=90 dir=-1
5 stand=100 dir=-1
6 stand=65 dir=1
7 stand=90 dir=1
8 stand=90 dir=-1
leg 1–4 lift=15 depth=0 stride=28 lift%=25 lower%=25
```

## 恢复步骤

站姿/方向（需要先托住机器人，摆出目标站姿）：

```text
stop
stand record
stand direction 1 -1
stand direction 2 +1
stand direction 3 +1
stand direction 4 -1
stand direction 5 -1
stand direction 6 +1
stand direction 7 +1
stand direction 8 -1
stand save
```

方向值以备份里的 `dir=` 为准，不要照抄本示例。

步态（每条腿一次，五项必须给齐）：

```text
stop
walk set 1 LIFT DEPTH STRIDE LIFT% LOWER%
walk set 2 LIFT DEPTH STRIDE LIFT% LOWER%
walk set 3 LIFT DEPTH STRIDE LIFT% LOWER%
walk set 4 LIFT DEPTH STRIDE LIFT% LOWER%
walk save
```

恢复后发 `ws` 核对，确认八路 `stand/dir` 和四腿五项与备份一致。
