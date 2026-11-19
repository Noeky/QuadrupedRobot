"""Evaluate a trained PPO policy headlessly.

    python sim/eval_policy.py --model sim/ppo_quadruped.zip --mode walk --episodes 3
"""

import argparse

from stable_baselines3 import PPO

from env import QuadrupedEnv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="sim/ppo_quadruped.zip")
    parser.add_argument("--mode", choices=["stand", "walk"], default="walk")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--episodes", type=int, default=3)
    args = parser.parse_args()

    env = QuadrupedEnv(mode=args.mode, speed=args.speed)
    model = PPO.load(args.model, device="cpu")
    for ep in range(args.episodes):
        obs, _ = env.reset()
        total = 0.0
        steps = 0
        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total += reward
            steps += 1
            if terminated or truncated:
                break
        print(
            f"episode {ep + 1}: steps={steps} reward={total:.2f} "
            f"x={info['x']:.3f} y={info['y']:.3f} z={info['z']:.3f} "
            f"terminated={terminated}"
        )
    env.close()


if __name__ == "__main__":
    main()
