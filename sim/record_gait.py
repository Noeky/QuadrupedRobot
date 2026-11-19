"""Record the gait to an MP4 and a CSV without needing an interactive viewer.

Examples:
    python sim/record_gait.py --realistic --seconds 13.5
    python sim/record_gait.py --realistic --com-x 15 --seconds 5 --out sim/fall.mp4
    python sim/record_gait.py --seconds 13.5 --follow

The CSV contains time, body pose, height sensor, base targets and actual
(filtered) servo commands, so it can be compared with real-robot logs.
"""

import argparse
import csv
import math
from math import radians
from pathlib import Path

import cv2
import mujoco

from runner import CONTROL_DT, GaitRunner, apply_model_scales, attitude
from servo import ServoBank

XML = Path(__file__).with_name("quadruped.xml")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--direction", type=float, choices=[-1.0, 1.0], default=1.0)
    parser.add_argument("--turn", type=float, choices=[-1.0, 0.0, 1.0], default=0.0)
    parser.add_argument("--turn-gain", type=float, default=0.5)
    parser.add_argument("--seconds", type=float, default=13.5)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--out", default="sim/gait.mp4")
    parser.add_argument("--csv", default="sim/gait_log.csv")
    parser.add_argument("--follow", action="store_true",
                        help="keep the camera on the body instead of a fixed view")
    parser.add_argument("--tau", type=float, default=0.0)
    parser.add_argument("--deadband", type=float, default=0.0)
    parser.add_argument("--backlash", type=float, default=0.0)
    parser.add_argument("--max-rate", type=float, default=0.0)
    parser.add_argument("--realistic", action="store_true")
    parser.add_argument("--mass-scale", type=float, default=1.0)
    parser.add_argument("--torque-scale", type=float, default=1.0)
    parser.add_argument("--friction", type=float, default=0.0)
    parser.add_argument("--com-x", type=float, default=0.0)
    parser.add_argument("--com-y", type=float, default=0.0)
    args = parser.parse_args()

    if args.realistic:
        args.tau = 0.08
        args.deadband = 0.5
        args.backlash = 1.0
        args.max_rate = 600.0

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
    data = mujoco.MjData(model)
    servo = None
    if args.tau > 0 or args.deadband > 0 or args.backlash > 0 or args.max_rate > 0:
        servo = ServoBank(
            n=model.nu,
            tau=args.tau,
            deadband=radians(args.deadband),
            backlash=radians(args.backlash),
            max_rate=radians(args.max_rate) if args.max_rate > 0 else None,
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

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (args.width, args.height),
    )
    if not writer.isOpened():
        raise SystemExit(f"could not open video writer: {out}")

    renderer = mujoco.Renderer(model, args.height, args.width)
    camera = mujoco.MjvCamera()
    camera.lookat[:] = [0.08, 0.0, 0.045]
    camera.distance = 0.42
    camera.azimuth = 135.0
    camera.elevation = -18.0

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = csv_path.open("w", newline="", encoding="utf-8")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(
        ["t", "x", "y", "z", "roll_deg", "pitch_deg", "height_mm"]
        + [f"base{i}" for i in range(model.nu)]
        + [f"ctrl{i}" for i in range(model.nu)]
    )

    next_frame = 0.0
    frames = 0
    while runner.t < args.seconds and not runner.fell:
        runner.step()
        x, y, z = (float(v) for v in data.qpos[:3])
        roll, pitch = attitude(data.qpos)
        height = float(data.sensor("us_distance").data[0]) * 1000.0
        csv_writer.writerow(
            [runner.t, x, y, z, math.degrees(roll), math.degrees(pitch), height]
            + list(runner.last_base)
            + list(runner.last_ctrl)
        )
        if runner.t + 1e-9 >= next_frame:
            if args.follow:
                camera.lookat[:] = [x, y, 0.055]
            renderer.update_scene(data, camera=camera)
            frame = renderer.render()
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            frames += 1
            next_frame += 1.0 / args.fps

    writer.release()
    csv_file.close()
    renderer.close()
    m = runner.metrics()
    print(f"wrote {out} ({frames} frames), {csv_path}")
    print(
        f"t={m.time_s:.2f}s dx_gait={m.dx_gait_mm:.1f} mm "
        f"min_z={m.min_z_mm:.1f} mm yaw={m.final_yaw_deg:+.1f} deg fell={m.fell}"
    )


if __name__ == "__main__":
    main()
