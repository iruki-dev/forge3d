"""forge3d App — high-level game-loop abstraction.

Provides a decorator-driven API similar to popular game frameworks::

    import forge3d as f3d

    app = f3d.App("Physics Sandbox")
    ball = None

    @app.on_start
    def setup(world: f3d.World) -> None:
        global ball
        world.add_ground()
        ball = world.add_sphere(radius=0.4, position=(0, 0, 6))

    @app.on_update
    def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
        if inp.key_pressed(f3d.Key.SPACE):
            world.apply_impulse(ball, (0, 0, 8))

    app.run()

Signature flexibility
---------------------
``on_start`` callback may accept 0 or 1 argument (the ``World``).
``on_update`` callback may accept 0, 1 (world), 2 (world, dt), or
3 (world, dt, inp) arguments — missing arguments are simply not passed.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

_UNSET: Any = object()


class App:
    """High-level forge3d application with a managed physics + render loop.

    Parameters
    ----------
    title     : Window title (shown in windowed mode).
    width     : Render width in pixels.
    height    : Render height in pixels.
    fps       : Target frames per second; also the physics step rate.
    gravity   : World gravity vector (x, y, z) in m/s².

    Examples
    --------
    >>> app = f3d.App("My World", fps=60)
    >>> @app.on_start
    ... def setup(world):
    ...     world.add_ground()
    ...     world.add_box(position=(0, 0, 5))
    >>> @app.on_update
    ... def update(world, dt, inp):
    ...     if inp.key_held(f3d.Key.W):
    ...         world.apply_impulse(world.bodies[0], (0, 5*dt, 0))
    >>> app.run(max_frames=120)  # doctest: +SKIP
    """

    def __init__(
        self,
        title: str | Any = _UNSET,
        width: int = 1280,
        height: int = 720,
        fps: float = 60.0,
        gravity: Any = (0.0, 0.0, -9.81),
    ) -> None:
        from forge3d.facade import World

        self._world: World = World(gravity=gravity)
        # A title that was explicitly provided → open a real OS window.
        # If omitted, stay headless (avoids accidental window creation in tests).
        self._windowed = title is not _UNSET
        self._title = "forge3d" if title is _UNSET else title
        self._width = width
        self._height = height
        self._fps = float(fps)
        self._dt = 1.0 / self._fps

        self._on_start: Callable | None = None
        self._on_update: Callable | None = None
        self._on_render: Callable | None = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def world(self) -> Any:
        """The managed :class:`~forge3d.facade.World` instance."""
        return self._world

    @property
    def fps(self) -> float:
        """Target frames per second."""
        return self._fps

    @fps.setter
    def fps(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"fps must be positive, got {value}")
        self._fps = float(value)
        self._dt = 1.0 / self._fps

    # ── Decorator callbacks ───────────────────────────────────────────────────

    def on_start(self, func: Callable) -> Callable:
        """Register a callback called once before the game loop begins.

        Signature: ``fn()`` or ``fn(world)``
        """
        self._on_start = func
        return func

    def on_update(self, func: Callable) -> Callable:
        """Register a callback called every frame, before :meth:`World.step`.

        Signature: one of:
        - ``fn()``
        - ``fn(world)``
        - ``fn(world, dt)``
        - ``fn(world, dt, inp)``
        """
        self._on_update = func
        return func

    def on_render(self, func: Callable) -> Callable:
        """Register a callback called after :meth:`Viewer.draw` each frame.

        Signature: ``fn()`` or ``fn(world)`` or ``fn(world, viewer)``
        """
        self._on_render = func
        return func

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, max_frames: int | None = None) -> None:
        """Start the game loop.

        Initialises the viewer, fires :meth:`on_start`, then loops:
        1. Build :class:`~forge3d.input.Input` snapshot
        2. Call :meth:`on_update` with ``(world, dt, inp)``
        3. ``world.step(dt)``
        4. ``viewer.draw()``
        5. Fire :meth:`on_render` if registered
        6. Advance frame; stop when ``max_frames`` reached or window closed

        Parameters
        ----------
        max_frames : Maximum frames to render before stopping automatically.
                     ``None`` (default) runs until the window is closed or
                     the default headless limit is reached.
        """
        from forge3d.input import _InputBuilder
        from forge3d.viewer import Viewer

        # Fire on_start
        if self._on_start is not None:
            _call_flexible(self._on_start, self._world)

        viewer = Viewer(
            self._world,
            title=self._title if self._windowed else None,
            width=self._width,
            height=self._height,
            max_frames=max_frames,
        )

        # Headless-only fallback builder (windowed mode uses the renderer's
        # GLFW-wired InputBuilder via viewer.input instead)
        _headless_builder = _InputBuilder()

        while viewer.is_open:
            # In windowed mode viewer.input is updated by the GLFW callbacks
            # inside viewer.draw(); in headless mode use a plain builder.
            inp = viewer.input if self._windowed else _headless_builder.build()

            if self._on_update is not None:
                _call_flexible(self._on_update, self._world, self._dt, inp)

            self._world.step(self._dt)

            viewer.draw()

            if self._on_render is not None:
                _call_flexible(self._on_render, self._world, viewer)

            if not self._windowed:
                _headless_builder.end_frame()

        viewer.close()

    def __repr__(self) -> str:
        return f"App(title={self._title!r}, {self._width}×{self._height}, fps={self._fps:.0f})"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _call_flexible(func: Callable, *positional: Any) -> Any:
    """Call *func* with as many leading positional args as its signature allows.

    This lets users write ``fn(world)``, ``fn(world, dt)``, or
    ``fn(world, dt, inp)`` interchangeably — missing args are omitted.
    Works with regular functions, lambdas, and bound methods.
    """
    try:
        sig = inspect.signature(func)
        n = len(
            [
                p
                for p in sig.parameters.values()
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
        )
        # If a parameter has VAR_POSITIONAL (*args), pass everything
        has_var_positional = any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
        )
        if has_var_positional:
            return func(*positional)
        return func(*positional[:n])
    except (ValueError, TypeError):
        return func(*positional)
