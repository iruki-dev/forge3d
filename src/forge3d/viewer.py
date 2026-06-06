"""Viewer — realtime rendering loop for a forge3d World.

Two modes, same API
-------------------
**Headless** (default, no ``title``)::

    viewer = f3d.Viewer(world, width=800, height=600)
    while viewer.is_open:
        world.step()
        viewer.draw()          # → (H,W,3) ndarray

**Windowed** (real OS window, pass ``title``)::

    viewer = f3d.Viewer(world, width=1280, height=720, title="My Game")
    while viewer.is_open:     # False on window-close or ESC
        inp = viewer.input    # live keyboard + mouse
        world.step(dt=viewer.dt)
        viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
        viewer.draw()          # renders to screen, returns None
        viewer.draw_text("Score: 42", x=10, y=10)
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
    world      : World to observe.
    mode       : ``"realtime"`` is the only supported mode.
    width, height : Frame dimensions in pixels.
    title      : If given, open a real OS window (windowed mode).
                 If ``None`` (default), render offscreen (headless mode).
    fps        : Target frames per second in windowed mode (default 60).
    max_frames : Headless-mode auto-close after this many frames.
                 Ignored in windowed mode.  ``None`` = 300 (headless default).
    """

    DEFAULT_HEADLESS_FRAMES = 300

    def __init__(
        self,
        world: World,
        mode: str = "realtime",
        *,
        width: int = 800,
        height: int = 600,
        title: str | None = None,
        fps: int = 60,
        max_frames: int | None = None,
        controls: Any = None,
        shadow_resolution: int = 0,
        sky_color: tuple | None = None,
    ) -> None:
        if mode != "realtime":
            raise ValueError(f"Viewer mode={mode!r} is not implemented. Use mode='realtime'.")
        self._world = world
        self._width = width
        self._height = height
        self._title = title
        self._fps = fps
        self._max_frames = max_frames
        self._frame_count = 0
        self._renderer: Any = None
        self._closed = False
        self._shadow_resolution = shadow_resolution
        self._sky_color = sky_color

        # Windowed mode flag — set once renderer is created
        self._windowed = title is not None

        # Input (headless: always empty; windowed: from renderer)
        self._inp_builder: _InputBuilder = _InputBuilder()
        self._current_input: Input = EMPTY_INPUT

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """``True`` until the viewer is closed.

        Windowed mode: ``False`` when the user closes the window or presses ESC.
        Headless mode: ``False`` after *max_frames* frames.
        """
        if self._closed:
            return False
        if self._windowed:
            # Check renderer's is_open once it has been created
            if self._renderer is not None and not self._renderer.is_open:
                self._closed = True
                return False
            return True
        else:
            limit = (
                self._max_frames if self._max_frames is not None else self.DEFAULT_HEADLESS_FRAMES
            )
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
        """Per-frame keyboard/mouse state snapshot.

        Windowed mode: updated at the start of each :meth:`draw` call from
        real OS events.  Headless mode: always returns an empty snapshot.
        """
        if self._windowed and self._renderer is not None:
            return self._renderer.input
        return self._current_input

    @property
    def dt(self) -> float:
        """Frame time in seconds.

        Windowed mode: actual wall-clock time of the previous frame.
        Headless mode: fixed ``1/60`` s.
        """
        if self._windowed and self._renderer is not None:
            return self._renderer.dt
        return 1.0 / 60.0

    # ── Camera ────────────────────────────────────────────────────────────────

    def set_camera(self, cam: Any) -> None:
        """Set the camera for subsequent :meth:`draw` calls.

        Parameters
        ----------
        cam : :class:`~forge3d.render.snapshot.CameraSnapshot` or a camera
              controller (:class:`~forge3d.camera.OrbitCamera` etc.).
        """
        from forge3d.render.snapshot import CameraSnapshot

        if hasattr(cam, "to_snapshot"):
            cam = cam.to_snapshot()
        if isinstance(cam, CameraSnapshot):
            self._ensure_renderer()
            self._renderer.set_camera(cam)
        else:
            raise TypeError(
                f"set_camera() expects a CameraSnapshot or OrbitCamera/FollowCamera, "
                f"got {type(cam).__name__}"
            )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self) -> np.ndarray | None:
        """Render one frame.

        Windowed mode
            Processes OS events, flips the previous frame, renders the new
            frame. Returns ``None``. Call :meth:`draw_text` *after* this to
            overlay HUD elements — they appear on the same visual frame.

        Headless mode
            Returns an ``(H, W, 3)`` uint8 ndarray.  Updates
            :attr:`input` from the internal event builder.
        """
        if not self.is_open:
            return None

        self._ensure_renderer()
        snap = self._world.snapshot()

        if self._windowed:
            self._renderer.render(snap)
            self._frame_count += 1
            return None
        else:
            # Update input snapshot for headless (no-op in practice — input
            # is always empty without a window, but keeps the interface uniform)
            self._current_input = self._inp_builder.build()
            self._inp_builder.end_frame()
            frame = self._renderer.render(snap)
            self._frame_count += 1
            return frame

    def draw_text(
        self,
        text: str,
        x: int = 10,
        y: int = 10,
        size: int = 20,
        color: tuple = (1.0, 1.0, 1.0),
        bg_alpha: float = 0.6,
        anchor: str = "topleft",
    ) -> None:
        """Render a HUD text overlay on top of the current frame.

        Must be called *after* :meth:`draw`.

        Windowed mode: GPU resources are cached — identical calls in
        successive frames reuse the same texture (zero re-upload).

        Parameters
        ----------
        text      : Text to display.
        x, y      : Pixel position of the anchor point.
        size      : Font size in pixels.
        color     : RGB in [0, 1].
        bg_alpha  : Dark background rectangle opacity [0, 1].
        anchor    : ``"topleft"`` / ``"center"`` / ``"topright"``.
        """
        if self._renderer is None:
            return
        self._renderer.draw_text(text, x, y, size, color, bg_alpha, anchor)

    # ── Convenience helpers ───────────────────────────────────────────────────

    def run(
        self,
        dt: float | None = None,
        max_frames: int | None = None,
        collect_frames: bool = False,
    ) -> list[np.ndarray] | None:
        """Step + draw in a loop until the viewer closes.

        Parameters
        ----------
        dt            : Physics step size (default: 1/60 s).
        max_frames    : Override the frame limit for this run.
        collect_frames: If True, return all rendered frames (headless only).
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
        """Pause rendering (no-op placeholder for compatibility)."""
        self._paused = True

    def resume(self) -> None:
        """Resume after :meth:`pause`."""
        self._paused = False

    def step_once(self, dt: float | None = None) -> np.ndarray | None:
        """Advance one physics step and draw one frame (useful for debugging)."""
        self._world.step(dt)
        return self.draw()

    # ── FPS helpers ───────────────────────────────────────────────────────────

    def set_cursor_captured(self, captured: bool) -> None:
        """Lock (hide + raw motion) or release the OS cursor.

        Essential for FPS mouse-look. When cursor is captured, ESC releases it
        instead of closing the window. Only available in windowed mode.
        """
        if self._windowed:
            self._ensure_renderer()
            self._renderer.set_cursor_captured(captured)

    def set_excluded_names(self, names: set[str]) -> None:
        """Exclude specific body names from rendering (e.g. local player in FPS)."""
        if self._windowed:
            self._ensure_renderer()
            self._renderer.set_excluded_names(names)

    def draw_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple = (1.0, 1.0, 1.0),
        alpha: float = 0.8,
    ) -> None:
        """Draw a filled flat-colored rectangle on the HUD.

        Must be called *after* :meth:`draw`.  Coordinates are in pixels from
        the top-left corner of the window.
        """
        if self._renderer is not None:
            self._renderer.draw_rect(x, y, w, h, color, alpha)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release renderer resources and mark the viewer as closed."""
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._closed = True

    def __enter__(self) -> Viewer:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        mode = "windowed" if self._windowed else "headless"
        status = "closed" if self._closed else f"frame {self._frame_count}"
        return f"Viewer({mode}, {self._width}×{self._height}, {status})"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_renderer(self) -> None:
        if self._renderer is not None:
            return
        if self._windowed:
            from forge3d.render.realtime.window_renderer import WindowedRealtimeRenderer

            self._renderer = WindowedRealtimeRenderer(
                self._width,
                self._height,
                self._title,
                fps=self._fps,
                shadow_resolution=self._shadow_resolution,
                **({} if self._sky_color is None else {"sky_color": self._sky_color}),
            )
        else:
            from forge3d.render.realtime.renderer import RealtimeRenderer

            self._renderer = RealtimeRenderer(width=self._width, height=self._height)
