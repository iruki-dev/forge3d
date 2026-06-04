"""demos/interactive_robot.py — 학습된 로봇 팔을 실시간으로 테스트.

PPO로 학습된 UR5 도달 정책을 불러와 사용자가 지정한 목표 위치로
로봇 팔이 이동하는 모습을 실시간 터미널 시각화 + 영상으로 보여줍니다.

필요 패키지: stable-baselines3  (pip install stable-baselines3)

사용법:
    python demos/interactive_robot.py                     # 기본 모델 로드
    python demos/interactive_robot.py --model my/final_model.zip
    python demos/interactive_robot.py --quick-train       # 없으면 빠르게 학습

명령어 (실행 중):
    Enter / n   → 새 랜덤 목표
    x y z       → 목표 좌표 지정 (예: 0.3 0.2 0.5)
    r           → 10번 연속 실행 후 성공률 보고
    q / quit    → 종료
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

# ── ANSI 색상 코드 ────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def _c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + RESET


# ── 배너 ─────────────────────────────────────────────────────────────────────

def _banner() -> None:
    print()
    print(_c("╔══════════════════════════════════════════════════════╗", CYAN, BOLD))
    print(_c("║    forge3d — 인터랙티브 로봇 팔 테스터  🦾           ║", CYAN, BOLD))
    print(_c("╠══════════════════════════════════════════════════════╣", CYAN, BOLD))
    print(_c("║  학습된 PPO 정책으로 UR5 팔이 목표에 도달합니다      ║", CYAN))
    print(_c("╠══════════════════════════════════════════════════════╣", CYAN, BOLD))
    print(_c("║  명령어:                                             ║", CYAN))
    print(_c("║   Enter / n   → 새 랜덤 목표                        ║", CYAN))
    print(_c("║   x y z       → 직접 목표 지정  (예: 0.3 0.2 0.5)  ║", CYAN))
    print(_c("║   r           → 10회 성공률 측정                    ║", CYAN))
    print(_c("║   q           → 종료                                ║", CYAN))
    print(_c("╚══════════════════════════════════════════════════════╝", CYAN, BOLD))
    print()


# ── 실시간 디스플레이 ─────────────────────────────────────────────────────────

class LiveDisplay:
    """로봇 상태를 터미널에서 실시간으로 업데이트."""

    LINES = 8

    def __init__(self) -> None:
        self._first = True

    def _up(self) -> None:
        if not self._first:
            sys.stdout.write(f"\033[{self.LINES}A")

    def render(
        self,
        step: int,
        max_steps: int,
        ee_pos: np.ndarray,
        target: np.ndarray,
        dist: float,
        terminated: bool,
        truncated: bool,
    ) -> None:
        self._up()
        self._first = False

        bar_w = 24
        filled = int(bar_w * step / max_steps)
        bar = "█" * filled + "░" * (bar_w - filled)

        dist_bar_w = 20
        dist_ratio = max(0.0, 1.0 - dist / 1.0)
        dist_fill = int(dist_bar_w * dist_ratio)
        dist_bar = "▓" * dist_fill + "░" * (dist_bar_w - dist_fill)
        dist_color = GREEN if dist < 0.05 else (YELLOW if dist < 0.20 else RED)

        # 상태 표시
        if terminated:
            status = _c(" ✅ 도달 성공! ", GREEN, BOLD)
        elif truncated:
            status = _c(" ⏱ 시간 초과  ", YELLOW)
        else:
            status = _c("  실행 중...  ", DIM)

        lines = [
            "",
            f"  {'스텝':<8} [{bar}] {step:>3}/{max_steps}",
            f"  {'EE 위치':<8} [{ee_pos[0]:+.3f}, {ee_pos[1]:+.3f}, {ee_pos[2]:+.3f}]",
            f"  {'목표 위치':<8} [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]",
            f"  {'거리':<8} " + _c(f"[{dist_bar}]", dist_color) + f"  {dist:.4f} m",
            f"  {'상태':<8} {status}",
            "",
        ]
        # 빈 줄이 self.LINES개가 되도록 맞춤
        while len(lines) < self.LINES:
            lines.append("")

        for line in lines[:self.LINES]:
            print(f"\033[2K{line}")

    def clear(self) -> None:
        self._first = True


# ── 단일 에피소드 실행 ───────────────────────────────────────────────────────

def run_episode(
    model,
    target: np.ndarray | None,
    display: LiveDisplay,
    max_steps: int = 150,
    save_video: bool = True,
    video_path: str = "attempt.mp4",
) -> dict:
    """정책을 실행하고 결과 반환. 영상도 저장."""
    import imageio
    from apps.robot_rl.envs.reach_env import ReachEnv

    env = ReachEnv(render_mode="rgb_array", max_steps=max_steps)
    obs, info = env.reset(seed=int(time.time() * 1000) % 100000)

    # 목표 강제 설정
    if target is not None:
        env._target_pos = target.copy()
        # 관측값 내 목표 위치도 교체
        obs[9:12] = target.copy()

    frames = []
    result = {
        "success": False, "steps": 0,
        "final_dist": 1.0, "target": obs[9:12].copy(),
    }

    display.clear()

    for step in range(max_steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)

        frame = env.render()
        if frame is not None:
            frames.append(frame)

        ee_pos = obs[6:9]
        tgt = obs[9:12]
        dist = float(np.linalg.norm(ee_pos - tgt))

        display.render(step + 1, max_steps, ee_pos, tgt, dist,
                       terminated, truncated)

        if terminated or truncated:
            result.update({
                "success": bool(terminated),
                "steps": step + 1,
                "final_dist": dist,
                "target": tgt.copy(),
            })
            break
    else:
        ee_pos = obs[6:9]
        result["final_dist"] = float(np.linalg.norm(obs[6:9] - obs[9:12]))
        result["steps"] = max_steps

    env.close()

    if save_video and frames:
        writer = imageio.get_writer(video_path, fps=20, quality=7)
        for f in frames:
            writer.append_data(f)
        writer.close()

    return result


# ── 성공률 측정 ───────────────────────────────────────────────────────────────

def benchmark(model, n_trials: int = 10) -> None:
    """여러 랜덤 목표에서 성공률을 측정."""
    from apps.robot_rl.envs.reach_env import ReachEnv

    print()
    print(_c(f"  {n_trials}회 성공률 측정 중…", DIM))
    successes = 0
    dists = []
    env = ReachEnv(max_steps=150)

    for i in range(n_trials):
        obs, _ = env.reset(seed=i * 13 + 7)
        for _ in range(150):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                successes += int(terminated)
                dists.append(info.get("dist", 1.0))
                break
        progress = "█" * (i + 1) + "░" * (n_trials - i - 1)
        print(f"\r  [{progress}] {i+1}/{n_trials}", end="", flush=True)

    env.close()
    print()

    sr = successes / n_trials
    sr_color = GREEN if sr >= 0.5 else (YELLOW if sr >= 0.2 else RED)
    print()
    print(_c("  ── 성능 측정 결과 ──", BOLD))
    print(f"  성공률:    {_c(f'{sr:.0%}', sr_color, BOLD)}  ({successes}/{n_trials})")
    print(f"  평균 거리: {np.mean(dists):.3f} m")
    print(f"  최소 거리: {np.min(dists):.3f} m")
    print()


# ── 목표 파싱 ─────────────────────────────────────────────────────────────────

def _parse_target(text: str) -> np.ndarray | None:
    """'x y z' 문자열을 np.ndarray로 변환. 실패 시 None 반환."""
    parts = text.strip().split()
    if len(parts) != 3:
        return None
    try:
        return np.array([float(p) for p in parts])
    except ValueError:
        return None


def _random_target() -> np.ndarray:
    """도달 가능한 랜덤 목표 생성."""
    rng = np.random.default_rng()
    r = rng.uniform(0.30, 0.65)
    theta = rng.uniform(-np.pi / 3, np.pi / 3)
    phi = rng.uniform(np.pi / 8, np.pi / 2.5)
    x = r * np.sin(phi) * np.cos(theta)
    y = r * np.sin(phi) * np.sin(theta)
    z = r * np.cos(phi)
    return np.array([x, y, z])


# ── 모델 로드 / 빠른 학습 ─────────────────────────────────────────────────────

def load_or_train(model_path: str | None, quick_train: bool) -> tuple:
    """모델을 로드하거나 빠르게 학습."""
    try:
        from stable_baselines3 import PPO
    except ImportError:
        print(_c("  ❌ stable-baselines3 가 설치되어 있지 않습니다.", RED))
        print("  설치 방법:  pip install stable-baselines3")
        print()
        print("  물리 엔진만 확인하려면:")
        print(f"    {_c('python demos/physics_showcase.py', CYAN)}")
        sys.exit(1)

    default_paths = [
        model_path,
        "training_output/reach_ppo/final_model.zip",
        "training_output/demo_run/final_model.zip",
    ]

    for path in default_paths:
        if path and os.path.exists(path):
            print(f"  모델 로드: {_c(path, CYAN)}")
            model = PPO.load(path)
            return model, path

    if quick_train:
        print(_c("  모델 없음 → 빠른 학습 시작 (50k 스텝, 약 3분)…", YELLOW))
        _quick_train()
        fallback = "training_output/quick_demo/final_model.zip"
        model = PPO.load(fallback)
        return model, fallback

    print(_c("  ❌ 학습된 모델을 찾을 수 없습니다.", RED))
    print("  해결 방법:")
    print(f"    1. {_c('python demos/training_watch.py', CYAN)}")
    print(f"    2. {_c('python demos/interactive_robot.py --quick-train', CYAN)}")
    sys.exit(1)


def _quick_train() -> None:
    """50k 스텝 빠른 학습."""
    from apps.robot_rl.envs.reach_env import ReachEnv
    from apps.robot_rl.training.callbacks import SuccessRateCallback
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor

    out = "training_output/quick_demo"
    os.makedirs(out, exist_ok=True)

    env = Monitor(ReachEnv())
    model = PPO("MlpPolicy", env, n_steps=1024, batch_size=128, n_epochs=10,
                learning_rate=3e-4, ent_coef=0.005, verbose=0)
    cb = SuccessRateCallback(log_path=os.path.join(out, "progress.csv"))

    total = 50_000
    for i in range(5):
        model.learn(total_timesteps=total // 5, reset_num_timesteps=(i == 0),
                    callback=cb, progress_bar=False)
        sr = cb.latest_success_rate
        done = (i + 1) * 20
        bar = "█" * done + "░" * (100 - done)
        print(f"\r  [{bar}] {done}%  성공률: {sr:.1%}", end="", flush=True)

    print()
    model.save(os.path.join(out, "final_model"))
    env.close()
    print(f"  모델 저장 → {out}/final_model.zip")


# ── 메인 루프 ────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="인터랙티브 로봇 팔 테스터")
    parser.add_argument("--model", type=str, default=None,
                        help="모델 파일 경로 (.zip)")
    parser.add_argument("--quick-train", action="store_true",
                        help="모델 없으면 50k 스텝 빠른 학습 후 시작")
    args = parser.parse_args()

    _banner()

    # 모델 로드
    model, model_path = load_or_train(args.model, args.quick_train)
    print("  모델 준비 완료. 명령을 입력하세요 (Enter = 랜덤 목표).\n")

    display = LiveDisplay()
    attempt_count = 0
    success_count = 0
    os.makedirs("demo_clips", exist_ok=True)

    # 첫 번째는 자동으로 랜덤 목표 실행
    target = _random_target()
    print(f"  첫 번째 목표: [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]")
    print()

    while True:
        attempt_count += 1
        video_path = f"demo_clips/attempt_{attempt_count:03d}.mp4"

        result = run_episode(model, target, display,
                             save_video=True, video_path=video_path)
        success_count += int(result["success"])

        # 결과 출력
        print()
        status_txt = _c("✅ 성공!", GREEN, BOLD) if result["success"] else _c("❌ 실패", RED)
        print(f"  {status_txt}  거리: {result['final_dist']:.4f}m  |  "
              f"스텝: {result['steps']}  |  "
              f"영상: {_c(video_path, DIM)}")
        sr_now = success_count / attempt_count
        sr_col = GREEN if sr_now >= 0.5 else YELLOW
        print(f"  누적 성공률: {success_count}/{attempt_count} "
              f"= {_c(f'{sr_now:.0%}', sr_col, BOLD)}")
        print()

        # 입력 대기
        try:
            user_input = input(_c("  명령 (Enter/n/x y z/r/q): ", BOLD)).strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "q"

        # 명령 처리
        cmd = user_input.lower()

        if cmd in ("q", "quit", "exit"):
            break

        if cmd in ("", "n", "new"):
            target = _random_target()
            print(f"  새 목표: [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]")
            print()

        elif cmd in ("r", "bench", "benchmark"):
            benchmark(model, n_trials=10)
            target = _random_target()

        else:
            parsed = _parse_target(user_input)
            if parsed is not None:
                target = parsed
                print(f"  목표 설정: [{target[0]:+.3f}, {target[1]:+.3f}, {target[2]:+.3f}]")
                print()
            else:
                print(_c(f"  ⚠ 인식 못함: '{user_input}'. "
                         f"'x y z' 형식으로 입력하거나 Enter를 누르세요.", YELLOW))
                print()
                target = _random_target()

    # 종료 요약
    print()
    print(_c("╔══════════════════════════════════════════════════════╗", CYAN, BOLD))
    print(_c("║                 세션 종료 요약                       ║", CYAN, BOLD))
    print(_c("╠══════════════════════════════════════════════════════╣", CYAN, BOLD))
    print(_c(f"║  총 시도: {attempt_count:>3}회{'':<43}║", CYAN))
    final_sr = success_count / max(attempt_count, 1)
    print(_c(f"║  성공:    {success_count:>3}회 ({final_sr:.0%}){'':<41}║", CYAN))
    print(_c(f"║  영상:    demo_clips/ 폴더에 저장됨{'':<18}║", CYAN))
    print(_c("╚══════════════════════════════════════════════════════╝", CYAN, BOLD))
    print()
    if attempt_count > 0:
        print("  영상 재생: mpv demo_clips/attempt_001.mp4")
    print()


if __name__ == "__main__":
    main()
