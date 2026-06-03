"""forge3d camera controllers.

Controllers compute a :class:`~forge3d.render.snapshot.CameraSnapshot` from
user-facing parameters (distance, angles, target) and can be driven by
:class:`~forge3d.input.Input` events each frame.

Usage::

    cam = f3d.OrbitCamera(target=(0, 0, 1), distance=10, elevation=30)

    while viewer.is_open:
        inp = viewer.input
        if inp.mouse_button(1):               # right-drag to orbit
            dx, dy = inp.mouse_delta()
            cam.rotate(d_azimuth=dx * 0.4, d_elevation=-dy * 0.4)
        cam.zoom(inp.scroll_delta() * 0.5)
        viewer.set_camera(cam.to_snapshot())
        world.step()
        viewer.draw()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.facade import Body
    from forge3d.render.snapshot import CameraSnapshot


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / (n + 1e-12)


# ── OrbitCamera ───────────────────────────────────────────────────────────────


class OrbitCamera:
    """Spherical-coordinate camera that orbits a target point.

    The camera is always looking at *target* from a point on a sphere of
    radius *distance*.  *azimuth* (yaw) rotates around the z-axis;
    *elevation* (pitch) tilts above/below the horizon.

    Parameters
    ----------
    target    : Point the camera looks at, world-frame (x, y, z).
    distance  : Eye-to-target distance in metres.
    azimuth   : Horizontal angle in degrees (0 = +x axis).
    elevation : Vertical angle in degrees above the horizon (clamped ±89°).
    fov_deg   : Vertical field-of-view in degrees.

    Usage::

        cam = f3d.OrbitCamera(target=(0, 0, 1), distance=8)
        cam.rotate(d_azimuth=45)         # spin 45° around target
        cam.zoom(2)                      # move 20% closer (delta > 0 = closer)
        snap = cam.to_snapshot()
        viewer.set_camera(snap)
    """

    def __init__(
        self,
        target: Any = (0.0, 0.0, 0.0),
        distance: float = 10.0,
        azimuth: float = 45.0,
        elevation: float = 30.0,
        fov_deg: float = 45.0,
    ) -> None:
        self.target = np.asarray(target, dtype=float)
        self.distance = max(0.05, float(distance))
        self.azimuth = float(azimuth)
        self.elevation = float(np.clip(elevation, -89.0, 89.0))
        self.fov_deg = float(fov_deg)

    # ── Derived geometry ──────────────────────────────────────────────────────

    @property
    def position(self) -> np.ndarray:
        """Current world-space eye position."""
        az = np.radians(self.azimuth)
        el = np.radians(self.elevation)
        x = self.distance * np.cos(el) * np.cos(az)
        y = self.distance * np.cos(el) * np.sin(az)
        z = self.distance * np.sin(el)
        return self.target + np.array([x, y, z])

    @property
    def _right(self) -> np.ndarray:
        az = np.radians(self.azimuth)
        return np.array([-np.sin(az), np.cos(az), 0.0])

    @property
    def _up_screen(self) -> np.ndarray:
        fwd = _normalize(self.target - self.position)
        return _normalize(np.cross(self._right, fwd))

    # ── Manipulation ──────────────────────────────────────────────────────────

    def rotate(self, d_azimuth: float = 0.0, d_elevation: float = 0.0) -> OrbitCamera:
        """Orbit around the target.

        Parameters
        ----------
        d_azimuth   : Azimuth delta in degrees.
        d_elevation : Elevation delta in degrees (clamped to ±89°).
        """
        self.azimuth += d_azimuth
        self.elevation = float(np.clip(self.elevation + d_elevation, -89.0, 89.0))
        return self

    def zoom(self, delta: float) -> OrbitCamera:
        """Adjust distance.

        *delta > 0* moves the camera closer; *delta < 0* moves it farther.
        The factor is ``distance *= (1 - delta * 0.1)`` so a delta of 1.0
        reduces distance by 10%.

        Parameters
        ----------
        delta : Zoom speed; typically ``Input.scroll_delta()``.
        """
        self.distance = max(0.05, self.distance * (1.0 - delta * 0.1))
        return self

    def set_distance(self, d: float) -> OrbitCamera:
        """Directly set the eye-to-target distance."""
        self.distance = max(0.05, float(d))
        return self

    def pan(self, dx: float, dy: float) -> OrbitCamera:
        """Translate the *target* point in screen space.

        Useful for middle-mouse-button panning.

        Parameters
        ----------
        dx, dy : Pixel offsets in screen space.
        """
        pan_speed = self.distance * 0.001
        self.target += self._right * (-dx * pan_speed) + self._up_screen * (dy * pan_speed)
        return self

    def look_at(self, target: Any) -> OrbitCamera:
        """Point the camera at a new target without changing distance."""
        self.target = np.asarray(target, dtype=float)
        return self

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def to_snapshot(self) -> CameraSnapshot:
        """Build a :class:`~forge3d.render.snapshot.CameraSnapshot` from the
        current orbit state — suitable for :meth:`Viewer.set_camera`.
        """
        from forge3d.render.snapshot import CameraSnapshot

        return CameraSnapshot(
            position=self.position.copy(),
            target=self.target.copy(),
            up=np.array([0.0, 0.0, 1.0]),
            fov_deg=self.fov_deg,
        )

    def __repr__(self) -> str:
        return (
            f"OrbitCamera(target={self.target.round(2).tolist()}, "
            f"az={self.azimuth:.1f}°, el={self.elevation:.1f}°, "
            f"d={self.distance:.2f} m)"
        )


# ── FollowCamera ──────────────────────────────────────────────────────────────


class FollowCamera:
    """Camera that smoothly tracks a :class:`~forge3d.facade.Body`.

    The camera sits at *body.position + offset* and looks at *body.position*.
    A smoothing factor ``alpha`` low-pass filters position changes
    (0 = frozen, 1 = instant snap).

    Parameters
    ----------
    body    : The :class:`Body` to follow.
    offset  : Camera offset from the body in world frame (x, y, z).
    alpha   : Smoothing factor per frame [0, 1].  Default 0.1 (smooth).
    fov_deg : Vertical field-of-view.

    Usage::

        cam = f3d.FollowCamera(ball, offset=(0, -8, 4), alpha=0.08)
        # each frame:
        viewer.set_camera(cam.to_snapshot())
    """

    def __init__(
        self,
        body: Body,
        offset: Any = (0.0, -8.0, 4.0),
        alpha: float = 0.1,
        fov_deg: float = 45.0,
    ) -> None:
        self._body = body
        self.offset = np.asarray(offset, dtype=float)
        self.alpha = float(np.clip(alpha, 0.0, 1.0))
        self.fov_deg = float(fov_deg)
        # Smoothed eye position — initialised to exact value
        self._eye: np.ndarray = body.position + self.offset

    def to_snapshot(self) -> CameraSnapshot:
        """Update smoothed position and return a CameraSnapshot."""
        from forge3d.render.snapshot import CameraSnapshot

        target = self._body.position.copy()
        desired_eye = target + self.offset
        self._eye = self._eye + self.alpha * (desired_eye - self._eye)

        return CameraSnapshot(
            position=self._eye.copy(),
            target=target,
            up=np.array([0.0, 0.0, 1.0]),
            fov_deg=self.fov_deg,
        )

    def __repr__(self) -> str:
        return (
            f"FollowCamera(body={self._body!r}, "
            f"offset={self.offset.tolist()}, alpha={self.alpha:.2f})"
        )
