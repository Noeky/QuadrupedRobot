"""Plot a gait CSV produced by record_gait.py.

    python sim/plot_log.py --csv sim/gait_log.csv --out sim/gait_plot.png
"""

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="sim/gait_log.csv")
    parser.add_argument("--out", default="sim/gait_plot.png")
    parser.add_argument("--joint", type=int, default=0, help="0..7")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    ax = axes[0, 0]
    ax.plot(df["t"], df["x"] * 1000, label="x forward")
    ax.plot(df["t"], df["y"] * 1000, label="y left")
    ax.set_ylabel("mm")
    ax.set_title("Body position")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(df["t"], df["z"] * 1000, label="body z")
    ax.plot(df["t"], df["height_mm"], label="height sensor")
    ax.set_ylabel("mm")
    ax.set_title("Height")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(df["t"], df["roll_deg"], label="roll")
    ax.plot(df["t"], df["pitch_deg"], label="pitch")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("deg")
    ax.set_title("Attitude")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(df["t"], df[f"base{args.joint}"], label=f"base{args.joint} target")
    ax.plot(df["t"], df[f"ctrl{args.joint}"], label=f"ctrl{args.joint} actual")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("rad")
    ax.set_title(f"Servo joint {args.joint}: target vs actual")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(args.out, dpi=140)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
