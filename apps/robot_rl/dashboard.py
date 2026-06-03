"""Learning curve dashboard — reads training CSV and saves matplotlib figure.

Usage
-----
    python apps/robot_rl/dashboard.py training_output/reach_ppo/logs/progress.csv

or from Python:
    from apps.robot_rl.dashboard import generate_dashboard
    generate_dashboard("logs/progress.csv", "dashboard.png")
"""

from __future__ import annotations

import csv
import os
import sys


def load_csv(path: str) -> dict[str, list[float]]:
    """Load training CSV into column arrays."""
    data: dict[str, list[float]] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                data.setdefault(k, [])
                try:
                    data[k].append(float(v))
                except ValueError:
                    pass
    return data


def generate_dashboard(csv_path: str, out_png: str = "dashboard.png") -> None:
    """Read training log CSV and write a 3-panel learning curve figure."""
    import matplotlib

    matplotlib.use("Agg")  # headless backend
    import matplotlib.pyplot as plt

    if not os.path.exists(csv_path):
        print(f"[dashboard] CSV not found: {csv_path}")
        return

    data = load_csv(csv_path)
    if not data or "timestep" not in data:
        print("[dashboard] Empty or malformed CSV")
        return

    steps = data["timestep"]
    success = data.get("success_rate", [0.0] * len(steps))
    reward = data.get("mean_reward", [0.0] * len(steps))
    ep_len = data.get("mean_ep_length", [0.0] * len(steps))

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    fig.suptitle("forge3d — Reaching PPO Training", fontsize=13, fontweight="bold")

    # ── subplot 1: mean episode reward ───────────────────────────────────────
    ax = axes[0]
    ax.plot(steps, reward, color="steelblue", lw=1.5)
    ax.set_ylabel("Mean Episode Reward")
    ax.set_ylim(bottom=None)
    ax.axhline(0, color="gray", lw=0.5, ls="--")
    ax.grid(True, alpha=0.3)

    # ── subplot 2: success rate ───────────────────────────────────────────────
    ax = axes[1]
    ax.plot(steps, [s * 100 for s in success], color="forestgreen", lw=1.5)
    ax.set_ylabel("Success Rate (%)")
    ax.set_ylim(-2, 102)
    ax.axhline(0, color="gray", lw=0.5, ls="--")
    ax.grid(True, alpha=0.3)
    # Annotate final value
    if success:
        final_sr = success[-1] * 100
        ax.annotate(
            f"{final_sr:.1f}%",
            xy=(steps[-1], final_sr),
            xytext=(-40, 8),
            textcoords="offset points",
            fontsize=9,
            color="forestgreen",
        )

    # ── subplot 3: mean episode length ────────────────────────────────────────
    ax = axes[2]
    ax.plot(steps, ep_len, color="darkorange", lw=1.5)
    ax.set_ylabel("Mean Episode Length")
    ax.set_xlabel("Environment Steps")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_png, dpi=120)
    plt.close(fig)
    print(f"[dashboard] Saved → {out_png}")
    if success:
        print(f"[dashboard] Final success rate: {success[-1] * 100:.1f}%")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apps/robot_rl/dashboard.py <csv_path> [out.png]")
        sys.exit(1)
    csv_in = sys.argv[1]
    png_out = sys.argv[2] if len(sys.argv) > 2 else "dashboard.png"
    generate_dashboard(csv_in, png_out)
