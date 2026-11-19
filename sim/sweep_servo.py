"""Sweep servo lag/deadband/backlash and report gait outcome.

Each trial: 1.5 s transition + three 4 s gait cycles at the chosen speed.
This is a quick way to see which non-ideal servo parameters reproduce the
real robot's instability.

Examples:
    python sim/sweep_servo.py
    python sim/sweep_servo.py --taus 0,0.05,0.1,0.15 --deadbands 0,0.5,1.0 --backlashes 0,0.5,1.0
    python sim/sweep_servo.py --taus 0 --deadbands 1 --backlashes 1 --max-rate 600
"""

import argparse
import csv
from math import radians
from pathlib import Path

import mujoco

from runner import GaitRunner, apply_model_scales
from servo import ServoBank

XML = Path(__file__).with_name("quadruped.xml")


def parse_list(text: str) -> list[float]:
    return [float(v) for v in text.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taus", default="0,0.05,0.10,0.15")
    parser.add_argument("--deadbands", default="0,0.5,1.0")
    parser.add_argument("--backlashes", default="0,0.5,1.0")
    parser.add_argument("--max-rate", type=float, default=0.0,
                        help="deg/s; 0 disables")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--seconds", type=float, default=13.5,
                        help="1.5 s transition + 3 gait cycles at 1x")
    parser.add_argument("--mass-scale", type=float, default=1.0)
    parser.add_argument("--torque-scale", type=float, default=1.0)
    parser.add_argument("--friction", type=float, default=0.0)
    parser.add_argument("--com-x", type=float, default=0.0,
                        help="torso CoM offset forward in mm")
    parser.add_argument("--com-y", type=float, default=0.0,
                        help="torso CoM offset left in mm")
    parser.add_argument("--csv", default="")
    args = parser.parse_args()

    if not XML.exists():
        from build_model import build_xml

        XML.write_text(build_xml(), encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(XML))
    apply_model_scales(
        model,
        args.mass_scale,
        args.torque_scale,
        args.friction,
        args.com_x / 1000.0,
        args.com_y / 1000.0,
    )
    print(
        f"mass_scale={args.mass_scale:.2f} torque_scale={args.torque_scale:.2f} "
        f"friction={args.friction:.2f} com=({args.com_x:.1f},{args.com_y:.1f}) mm"
    )
    taus = parse_list(args.taus)
    deadbands = parse_list(args.deadbands)
    backlashes = parse_list(args.backlashes)

    rows = []
    print(f"{'tau_ms':>7} {'dead_deg':>9} {'back_deg':>9} "
          f"{'dx_mm':>8} {'min_z':>8} {'max_y':>8} {'fell':>5}")
    for tau in taus:
        for dead in deadbands:
            for back in backlashes:
                data = mujoco.MjData(model)
                servo = ServoBank(
                    n=model.nu,
                    tau=tau,
                    deadband=radians(dead),
                    backlash=radians(back),
                    max_rate=radians(args.max_rate) if args.max_rate > 0 else None,
                )
                runner = GaitRunner(model, data, speed=args.speed, servo=servo)
                m = runner.run(args.seconds)
                row = {
                    "tau_ms": tau * 1000,
                    "dead_deg": dead,
                    "back_deg": back,
                    "dx_mm": m.dx_gait_mm,
                    "min_z_mm": m.min_z_mm,
                    "max_y_mm": m.max_abs_y_mm,
                    "fell": int(m.fell),
                }
                rows.append(row)
                print(
                    f"{row['tau_ms']:7.1f} {row['dead_deg']:9.2f} {row['back_deg']:9.2f} "
                    f"{row['dx_mm']:8.1f} {row['min_z_mm']:8.1f} {row['max_y_mm']:8.1f} "
                    f"{row['fell']:5d}"
                )

    if args.csv:
        out = Path(args.csv)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
