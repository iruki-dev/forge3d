"""OpenGL context creation — window or headless (Xvfb).

This environment has no GPU but Xvfb + Mesa llvmpipe provides software OpenGL.
Strategy:
  1. If DISPLAY is set, try to create a standalone moderngl context directly.
  2. Otherwise, launch Xvfb :99 as a subprocess and point DISPLAY to it.
  3. If moderngl is not installed or context creation fails, raise RuntimeError.

CLAUDE.md §0: OpenGL for graphics is permitted even on "GPU-unavailable" hosts.
We confirmed that llvmpipe via Xvfb works in this container.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any


class XvfbProcess:
    """Manages a Xvfb virtual framebuffer subprocess."""

    _DISPLAY = ":97"  # unique display number to avoid conflict with system :99

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self._proc: subprocess.Popen | None = None
        self._width = width
        self._height = height
        self._prev_display: str | None = None

    def start(self) -> None:
        if self._proc is not None:
            return  # already running
        self._prev_display = os.environ.get("DISPLAY")
        self._proc = subprocess.Popen(
            [
                "Xvfb",
                self._DISPLAY,
                "-screen",
                "0",
                f"{self._width}x{self._height}x24",
                "-ac",
                "+extension",
                "GLX",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.environ["DISPLAY"] = self._DISPLAY
        time.sleep(0.4)  # wait for Xvfb to initialize

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=3)
            self._proc = None
        # Restore DISPLAY
        if self._prev_display is not None:
            os.environ["DISPLAY"] = self._prev_display
        elif "DISPLAY" in os.environ:
            del os.environ["DISPLAY"]

    def __enter__(self) -> XvfbProcess:
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()


def create_standalone_context(
    width: int = 800,
    height: int = 600,
) -> tuple[Any, XvfbProcess | None]:
    """Create a moderngl standalone (offscreen) context.

    Returns
    -------
    ctx   : moderngl.Context
    xvfb  : XvfbProcess | None  — caller must call xvfb.stop() when done
    """
    try:
        import moderngl
    except ImportError as exc:
        raise RuntimeError("moderngl is not installed. Run: pip install moderngl") from exc

    xvfb: XvfbProcess | None = None

    # Try existing display first
    if "DISPLAY" in os.environ:
        try:
            ctx = moderngl.create_standalone_context()
            return ctx, None
        except Exception:
            pass  # fall through to Xvfb

    # Try Xvfb
    try:
        xvfb = XvfbProcess(width, height)
        xvfb.start()
        ctx = moderngl.create_standalone_context()
        return ctx, xvfb
    except Exception as exc:
        if xvfb:
            xvfb.stop()
        raise RuntimeError(f"Cannot create OpenGL context (tried DISPLAY and Xvfb): {exc}") from exc


def check_opengl_available() -> bool:
    """Return True if a standalone OpenGL context can be created."""
    try:
        ctx, xvfb = create_standalone_context()
        ctx.release()
        if xvfb:
            xvfb.stop()
        return True
    except Exception:
        return False
