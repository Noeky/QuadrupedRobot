"""PPO smoke training for the quadruped residual policy.

Install:
    python -m pip install gymnasium stable-baselines3 -i https://pypi.tuna.tsinghua.edu.cn/simple

Examples:
    python sim/train_ppo.py --mode stand --steps 20000
    python sim/train_ppo.py --mode walk --steps 200000 --out sim/ppo_walk

The script is a starting point, not a tuned result.  Start with `stand` to
verify the pipeline, then `walk` with the scripted gait as the base policy.
"""

import argparse
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

from env import QuadrupedEnv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["stand", "walk"], default="stand")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--out", type=str, default="sim/ppo_quadruped")
    parser.add_argument("--randomize", action="store_true")
    args = parser.parse_args()

    env = QuadrupedEnv(mode=args.mode, speed=args.speed, randomize=args.randomize)
    check_env(env, warn=True)
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        n_steps=256,
        batch_size=64,
        n_epochs=10,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        device="cpu",
    )
    model.learn(total_timesteps=args.steps, progress_bar=False)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out))
    print(f"saved {out}.zip")


if __name__ == "__main__":
    main()
