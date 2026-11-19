# 板内参数备份

> 规则：任何 `walk save`、`stand save` 或重刷固件之前，先运行 `ws`，把全文粘贴到下面的“当前备份”。
> 正常 Arduino 上传不会清 NVS；Tools → **Erase All Flash Before Sketch Upload** 必须保持 Disabled。
> `walk set`、`walk speed`、`walk deadband` 只改 RAM，断电/重启后恢复板内保存值，可安全试。

## 兼容性说明

2026-11-19 加入前进/后退/左右转时，没有修改 `profile-v2`（站姿/方向）或 `legs-v2`（四腿步态）的二进制结构；正常 Arduino 上传会保留板内现有标定和步态。`walk turn` 的差速增益是 RAM-only，不属于存档。用本文件的当前 stand/dir/LegTuning 计算，前进/后退/左右转的命令角范围约 65～111°，均在 0～180° 内，不需要为转向重新标定。新固件 `ws` 会多一行 `motion=...`，原有 stand/dir/leg 行不变。

`foot offset MM` 也是 RAM-only；它同时平移 `stand` 目标与步态足端轨迹，负值=足端后移。若要把偏移固化，先 `foot offset X`、`stand`，再 `stand record`（记录时自动把 offset 归零）和 `stand save`，这会覆盖 `quad-walk` 的站姿/方向；`legs-v2` 不变，不需要 `walk save`。

## 参数存放位置

| 内容 | NVS 命名空间 | 写入命令 | 读取/恢复 |
|---|---|---|---|
| 站姿角、8 路方向 | `quad-walk` | `stand save` | 开机自动读；`stand load` |
| 四腿 lift/depth/stride/lift%/lower% | `quad-gait` | `walk save` | 开机自动读；`walk load` |
| Wi-Fi 配置 | `quad-net` | 手机页面保存 | 开机自动读 |

`speed` 和 `deadband` 只存在 RAM，重启回到 1.0 和 1。

## 当前备份

备份时间：2026-11-19 17:24:05（状态头、1–2 路）；17:21:54（3–8 路、四腿）。两次读数一致，合并如下。

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
leg 1 lift=15.000 depth=0.000 stride=28.000 lift%=25.00 lower%=25.00
leg 2 lift=15.000 depth=0.000 stride=28.000 lift%=25.00 lower%=25.00
leg 3 lift=15.000 depth=0.000 stride=28.000 lift%=25.00 lower%=25.00
leg 4 lift=15.000 depth=0.000 stride=28.000 lift%=25.00 lower%=25.00
```

已确认：

- `standCaptured=1`、`ready=1`，8 路方向均非 0；方向模式与 README 的 `-1,+1,+1,-1,-1,+1,+1,-1` 完全一致。
- 四腿步态都是默认值；`speed=1.00`、`deadband=1.00` 是 RAM 值，重启会回默认。
- 这是当前完整基线。以后任何 `walk save` / `stand save` 前先与这段对比。

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
