"""Recorder — capture simulation frames to video or image sequence.

P4 status:
  - ``mode='realtime'`` : captures frames from the realtime renderer (works now).
  - ``mode='hq'``       : high-quality software raytracer — NOT YET IMPLEMENTED
                          (planned for P6; raises ``NotImplementedError``).

Usage::

    world = forge3d.World()
    world.add_ground()
    ball = world.add_sphere(radius=0.5, position=(0, 0, 4), restitution=0.8)
    rec  = forge3d.Recorder(world, mode="realtime", output="bounce.mp4")
    rec.run(duration=3.0, dt=1/240, fps=60)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.facade import World


class Recorder:
    """Capture a World's simulation as video frames.

    Parameters
    ----------
    world      : World to record.  May be ``None`` when only ``run_policy``
                 will be used (no free-simulation recording).
    mode       : ``'realtime'`` or ``'hq'``.
    resolution : (width, height) in pixels.
    output     : Output file path (mp4 via imageio, or image sequence dir).
    samples    : Ray samples per pixel for HQ mode (ignored in realtime).
    """

    def __init__(
        self,
        world: World | None = None,
        mode: str = "realtime",
        resolution: tuple[int, int] = (800, 600),
        output: str = "output.mp4",
        samples: int = 64,
    ) -> None:
        self._world = world
        self._mode = mode
        self._resolution = resolution
        self._output = output
        self._samples = samples

    # ── Recording ─────────────────────────────────────────────────────────────

    def run(
        self,
        duration: float,
        dt: float = 1.0 / 240.0,
        fps: float = 60.0,
    ) -> None:
        """Simulate for *duration* seconds and save video.

        Physics runs at ``dt`` timestep; frames are saved at ``fps`` rate.
        So ``phys_steps_per_frame = round(1/(fps*dt))``.

        Parameters
        ----------
        duration : Simulation duration in seconds.
        dt       : Physics integration step.
        fps      : Output video frame rate.
        """
        if self._world is None:
            raise RuntimeError(
                "Recorder.run() requires a World object. "
                "Pass world= when constructing, or use run_policy() for policy rollouts."
            )
        w, h = self._resolution
        n_frames = max(1, int(round(duration * fps)))
        phys_per_frame = max(1, int(round(1.0 / (fps * dt))))

        print(
            f"Recording {n_frames} frames @ {fps:.0f} fps  "
            f"(mode={self._mode}, dt={dt:.4f}s, {phys_per_frame} physics steps/frame)"
        )

        if self._mode == "hq":
            from forge3d.render.hq.renderer import HQRenderer

            renderer: Any = HQRenderer(width=w, height=h, samples=self._samples)
        else:
            from forge3d.render.realtime.renderer import RealtimeRenderer

            renderer = RealtimeRenderer(width=w, height=h)

        frames: list[np.ndarray] = []
        with renderer:
            for i in range(n_frames):
                for _ in range(phys_per_frame):
                    self._world.step(dt)
                snap = self._world.snapshot()
                frame = renderer.render(snap)
                if frame is not None:
                    frames.append(frame)
                if i % max(1, n_frames // 5) == 0:
                    print(f"  [{i + 1:4d}/{n_frames}]  t={self._world.time:.2f}s")

        self._save(frames, fps)

    def run_policy(
        self,
        policy: Any,
        env: Any,
        duration: float = 5.0,
        fps: float = 24.0,
        deterministic: bool = True,
        seed: int = 0,
    ) -> None:
        """Record a trained policy rollout from a Gymnasium-compatible env.

        Parameters
        ----------
        policy      : SB3 model or any object with ``predict(obs)`` method.
        env         : Gymnasium env (must support ``render_mode="rgb_array"``).
        duration    : Recording duration in seconds.
        fps         : Output video frame rate.
        deterministic : Use deterministic policy actions.
        seed        : Env reset seed.
        """
        n_frames = max(1, int(round(duration * fps)))
        obs, _ = env.reset(seed=seed)

        frames: list[np.ndarray] = []
        for _ in range(n_frames):
            action, _ = policy.predict(obs, deterministic=deterministic)
            obs, _reward, terminated, truncated, _info = env.step(action)
            if terminated or truncated:
                obs, _ = env.reset(seed=seed)
            frame = env.render()
            if frame is not None:
                frames.append(frame)

        if not frames:
            print("run_policy: no frames collected (env.render() returned None).")
            return

        self._save(frames, fps)
        print(f"Policy rollout saved: {self._output}  ({len(frames)} frames @ {fps:.0f} fps)")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _save(self, frames: list[np.ndarray], fps: float) -> None:
        """Save frames to the configured output path."""
        if not frames:
            print("No frames to save.")
            return

        ext = os.path.splitext(self._output)[1].lower()

        if ext in (".mp4", ".avi", ".gif", ".webm"):
            self._save_video(frames, fps)
        else:
            # Treat as directory for image sequence
            self._save_sequence(frames)

    def _save_video(self, frames: list[np.ndarray], fps: float) -> None:
        try:
            import imageio

            writer = imageio.get_writer(self._output, fps=fps)
            for f in frames:
                writer.append_data(f)
            writer.close()
            print(f"Saved: {self._output}  ({len(frames)} frames @ {fps:.0f} fps)")
        except ImportError:
            print(
                "imageio not installed — saving as image sequence instead.\n"
                "Install: pip install imageio imageio-ffmpeg"
            )
            self._save_sequence(frames)
        except Exception as e:
            print(f"Video save failed ({e}) — falling back to image sequence.")
            self._save_sequence(frames)

    def _save_sequence(self, frames: list[np.ndarray]) -> None:
        out_dir = os.path.splitext(self._output)[0]
        os.makedirs(out_dir, exist_ok=True)
        try:
            import imageio

            for i, f in enumerate(frames):
                imageio.imwrite(os.path.join(out_dir, f"frame_{i:04d}.png"), f)
        except ImportError:
            for i, f in enumerate(frames):
                _save_ppm(f, os.path.join(out_dir, f"frame_{i:04d}.ppm"))
        print(f"Saved {len(frames)} frames to: {out_dir}/")


def _save_ppm(frame: np.ndarray, path: str) -> None:
    h, w = frame.shape[:2]
    with open(path, "wb") as fh:
        fh.write(f"P6\n{w} {h}\n255\n".encode())
        fh.write(frame.tobytes())
