"""Run the firmware's diagonal trot in MuJoCo, optionally with a servo model.

Examples:
    python sim/run_gait.py                      # ideal viewer
    python sim/run_gait.py --realistic          # 80 ms lag, 0.5 deg deadband, 1 deg backlash
    python sim/run_gait.py --tau 0.12 --deadband 1.0 --backlash 1.5
    python sim/run_gait.py --seconds 13.5 --realistic   # headless, 3 gait cycles

Angle arguments are full widths in degrees.  The servo model is:
command -> deadband -> backlash -> first-order lag -> rate limit.
"""

import argparse
import time
from math import radians
from pathlib import Path

import mujoco
import mujoco.viewer

from runner import CONTROL_DT, GaitRunner, apply_model_scales
from servo import ServoBank

XML = Path(__file__).with_name("quadruped.xml")


def load():
    if not XML.exists():
        from build_model import build_xml

        XML.write_text(build_xml(), encoding="utf-8")
    model = mujoco.MjModel.from_xml_path(str(XML))
    data = mujoco.MjData(model)
    return model, data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed", type=float, default=1.0,
                        help="gait multiplier (default 1.0, cycle 4 s)")
    parser.add_argument("--direction", type=float, choices=[-1.0, 1.0], default=1.0,
                        help="+1 forward, -1 backward")
    parser.add_argument("--turn", type=float, choices=[-1.0, 0.0, 1.0], default=0.0,
                        help="+1 left, 0 straight, -1 right")
    parser.add_argument("--turn-gain", type=float, default=0.5,
                        help="differential stride gain (0..0.8)")
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="headless duration; 0 uses the viewer")
    parser.add_argument("--tau", type=float, default=0.0,
                        help="first-order servo lag time constant in seconds")
    parser.add_argument("--deadband", type=float, default=0.0,
                        help="servo command deadband, full width in degrees")
    parser.add_argument("--backlash", type=float, default=0.0,
                        help="gear backlash, full width in degrees")
    parser.add_argument("--max-rate", type=float, default=0.0,
                        help="servo slew limit in deg/s; 0 disables")
    parser.add_argument("--realistic", action="store_true",
                        help="shorthand for tau=0.08, deadband=0.5, backlash=1.0, max-rate=600")
    parser.add_argument("--mass-scale", type=float, default=1.0,
                        help="scale all body masses/inertias (e.g. 1.4)")
    parser.add_argument("--torque-scale", type=float, default=1.0,
                        help="scale all actuator torque limits (e.g. 0.6)")
    parser.add_argument("--friction", type=float, default=0.0,
                        help="override all geom sliding friction; 0 keeps the model")
    parser.add_argument("--com-x", type=float, default=0.0,
                        help="torso CoM offset forward in mm")
    parser.add_argument("--com-y", type=float, default=0.0,
                        help="torso CoM offset left in mm")
    args = parser.parse_args()

    if args.realistic:
        args.tau = 0.08
        args.deadband = 0.5
        args.backlash = 1.0
        args.max_rate = 600.0

    model, data = load()
    apply_model_scales(
        model,
        args.mass_scale,
        args.torque_scale,
        args.friction,
        args.com_x / 1000.0,
        args.com_y / 1000.0,
    )
    servo = None
    if args.tau > 0 or args.deadband > 0 or args.backlash > 0 or args.max_rate > 0:
        servo = ServoBank(
            n=model.nu,
            tau=args.tau,
            deadband=radians(args.deadband),
            backlash=radians(args.backlash),
            max_rate=radians(args.max_rate) if args.max_rate > 0 else None,
        )
    print(
        f"motion direction={args.direction:+.0f} turn={args.turn:+.0f} gain={args.turn_gain:.2f}"
    )
    print(
        f"gait speed={args.speed:.2f} tau={args.tau*1000:.0f} ms "
        f"deadband={args.deadband:.2f} deg backlash={args.backlash:.2f} deg "
        f"max_rate={args.max_rate:.0f} deg/s"
    )
    print(
        f"mass_scale={args.mass_scale:.2f} torque_scale={args.torque_scale:.2f} "
        f"friction={args.friction:.2f} com=({args.com_x:.1f},{args.com_y:.1f}) mm"
    )

    runner = GaitRunner(
        model,
        data,
        speed=args.speed,
        servo=servo,
        direction=args.direction,
        turn=args.turn,
        turn_gain=args.turn_gain,
    )
    if args.seconds <= 0:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running() and not runner.fell:
                start = time.perf_counter()
                runner.step()
                viewer.sync()
                remaining = CONTROL_DT - (time.perf_counter() - start)
                if remaining > 0:
                    time.sleep(remaining)
    else:
        runner.run(args.seconds)

    m = runner.metrics()
    print(
        f"t={m.time_s:.2f}s  dx_gait={m.dx_gait_mm:.1f} mm  "
        f"dx_total={m.dx_total_mm:.1f} mm"
    )
    print(
        f"min_z={m.min_z_mm:.1f} mm  final_z={m.final_z_mm:.1f} mm  "
        f"|y|max={m.max_abs_y_mm:.1f} mm  yaw={m.final_yaw_deg:+.1f} deg  fell={m.fell}"
    )


if __name__ == "__main__":
    main()
