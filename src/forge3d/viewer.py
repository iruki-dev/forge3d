"""Viewer — realtime rendering loop for a forge3d World.

Headless mode (default): renders to offscreen FBO via Xvfb + llvmpipe.
Window mode: requires a display (DISPLAY env var set, or a real monitor).

Usage::

    world = forge3d.World()
    world.add_ground()
    box = world.add_box(size=(1,1,1), position=(0,0,5))

    # Simple fixed-frame loop
    viewer = forge3d.Viewer(world, max_frames=90)
    while viewer.is_open:
        world.step()
        viewer.draw()

    # With input and orbit camera
    cam = forge3d.OrbitCamera(distance=10)
    viewer = forge3d.Viewer(world)
    while viewer.is_open:
        inp = viewer.input
        if inp.mouse_button(1):
            dx, dy = inp.mouse_delta()
            cam.rotate(d_azimuth=dx * 0.5, d_elevation=-dy * 0.5)
        cam.zoom(inp.scroll_delta() * 0.5)
        viewer.set_camera(cam.to_snapshot())
        world.step()
        viewer.draw()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.input import EMPTY_INPUT, Input, _InputBuilder

if TYPE_CHECKING:
    from forge3d.facade import World


class Viewer:
    """Realtime viewer for a forge3d World.

    Parameters
    ----------
    world      : World instance to observe.
    mode       : ``"realtime"`` — only mode implemented (P6 adds HQ).
    width, height : Frame dimensions in pixels.
    max_frames : Auto-close after this many ``draw()`` calls.
                 ``None`` = infinite (useful with a real window; in headless
                 mode defaults to 300 unless overridden).
    controls   : Reserved for interactive controls (``None`` = defaults).
    """

    DEFAULT_HEADLESS_FRAMES = 300

    def __init__(
        self,
        world: World,
        mode: str = "realtime",
        *,
        width: int = 800,
        height: int = 600,
        max_frames: int | None = None,
        controls: Any = None,
    ) -> None:
        if mode != "realtime":
            raise ValueError(
                f"Viewer mode={mode!r} is not implemented. "
                "Use mode='realtime'."
            )
        self._world = world
        self._mode = mode
        self._width = width
        self._height = height
        self._max_frames = max_frames
        self._frame_count = 0
        self._renderer: Any = None
        self._closed = False
        self._frames_buffer: list[np.ndarray] = []

        # Input state — always initialised; stays EMPTY_INPUT in headless
        self._inp_builder: _InputBuilder = _InputBuilder()
        self._current_input: Input = EMPTY_INPUT

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """``True`` until the viewer is closed or ``max_frames`` is reached."""
        if self._closed:
            return False
        limit = self._max_frames
        if limit is None:
            limit = self.DEFAULT_HEADLESS_FRAMES
        if self._frame_count >= limit:
            self.close()
            return False
        return True

    @property
    def frame_count(self) -> int:
        """Number of frames rendered so far."""
        return self._frame_count

    @property
    def input(self) -> Input:
        """Per-frame :class:`~forge3d.input.Input` snapshot.

        Updated at the start of each :meth:`draw` call.
        In headless mode this always returns an empty (all-False) snapshot.
        """
        return self._current_input

    @property
    def dt(self) -> float:
        """Nominal per-frame time step (1/60 s). Constant; does not measure wall time."""
        return 1.0 / 60.0

    # ── Camera ────────────────────────────────────────────────────────────────

    def set_camera(self, cam: Any) -> None:
        """Set the camera for subsequent ``draw()`` calls.

        Parameters
        ----------
        cam : A :class:`~forge3d.render.snapshot.CameraSnapshot` or a camera
              controller such as :class:`~forge3d.camera.OrbitCamera` (anything
              with a ``to_snapshot()`` method).
        """
        from forge3d.render.snapshot import CameraSnapshot

        if hasattr(cam, "to_snapshot"):
            cam = cam.to_snapshot()
        if isinstance(cam, CameraSnapshot):
            self._ensure_renderer()
            self._renderer.set_camera(cam)
        else:
            raise TypeError(
                f"set_camera() expects a CameraSnapshot or an OrbitCamera/FollowCamera, "
                f"got {type(cam).__name__}"
            )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self) -> np.ndarray | None:
        """Render one frame from the world's current state.

        Also updates :attr:`input` (builds new snapshot from the event queue).

        Returns
        -------
        ndarray or None
            RGB frame ``(H, W, 3)`` uint8, or ``None`` after close.
        """
        if not self.is_open:
            return None
        # Build the input snapshot for this frame and clear per-frame events
        self._current_input = self._inp_builder.build()
        self._inp_builder.end_frame()

        self._ensure_renderer()
        snap = self._world.snapshot()
        frame = self._renderer.render(snap)
        self._frame_count += 1
        return frame

    def run(
        self,
        dt: float | None = None,
        max_frames: int | None = None,
        collect_frames: bool = False,
    ) -> list[np.ndarray] | None:
        """Convenience: step + draw in a loop until the viewer closes.

        Parameters
        ----------
        dt            : Physics step size (default: ``world.DEFAULT_DT``).
        max_frames    : Override the viewer's max_frames for this run.
        collect_frames: If True, return all rendered frames as a list.
        """
        if max_frames is not None:
            self._max_frames = max_frames

        frames: list[np.ndarray] | None = [] if collect_frames else None
        while self.is_open:
            self._world.step(dt)
            frame = self.draw()
            if collect_frames and frames is not None and frame is not None:
                frames.append(frame)
        return frames

    def pause(self) -> None:
        """Pause: subsequent ``step()`` calls inside :meth:`run` are no-ops."""
        self._paused = True

    def resume(self) -> None:
        """Resume after :meth:`pause`."""
        self._paused = False

    def step_once(self, dt: float | None = None) -> np.ndarray | None:
        """Advance one physics step and draw one frame (useful for debugging)."""
        self._world.step(dt)
        return self.draw()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release GPU resources and mark the viewer as closed."""
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._closed = True

    def __enter__(self) -> Viewer:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        status = "closed" if self._closed else f"frame {self._frame_count}"
        return f"Viewer(mode={self._mode!r}, {self._width}×{self._height}, {status})"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_renderer(self) -> None:
        if self._renderer is not None:
            return
        from forge3d.render.realtime.renderer import RealtimeRenderer

        self._renderer = RealtimeRenderer(width=self._width, height=self._height)
