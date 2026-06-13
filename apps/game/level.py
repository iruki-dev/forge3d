"""FORGE RUNNER — level construction."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

import forge3d as f3d

GOLD = f3d.Material(color=(1.0, 0.78, 0.15), emissive=0.9, metallic=0.6, roughness=0.25)
CYAN = f3d.Material(color=(0.15, 0.9, 1.0), emissive=0.8, metallic=0.3, roughness=0.3)
LAVA = f3d.Material(color=(1.0, 0.28, 0.05), emissive=1.0, roughness=0.8)
STONE = f3d.Material(color=(0.52, 0.52, 0.58), roughness=0.85)
DARKSTONE = f3d.Material(color=(0.33, 0.33, 0.4), roughness=0.9)
WOOD = f3d.Material(color=(0.55, 0.38, 0.2), roughness=0.8)
STEEL = f3d.Material(color=(0.75, 0.78, 0.85), metallic=0.9, roughness=0.3)
GREEN = f3d.Material(color=(0.2, 0.95, 0.35), emissive=0.7)
RED = f3d.Material(color=(0.95, 0.15, 0.15), emissive=0.6)
GRASS = f3d.Material(color=(0.30, 0.47, 0.22), roughness=0.95)


@dataclass
class Core:
    marker: f3d.Body
    zone: object
    collected: bool = False
    spin: float = 0.0


class Level:
    """Builds and owns all static + scripted geometry."""

    def __init__(self, world: f3d.World):
        self.world = world
        self.cores: list[Core] = []
        self.checkpoints: list[tuple[object, np.ndarray, f3d.Body]] = []
        self.lava_zones: list = []
        self.spring_pads: list[tuple[object, float]] = []
        self.windmill_blades: list[f3d.Body] = []
        self.goal_zone = None
        self.goal_beam: f3d.Body | None = None
        self.spawn = np.array([-34.0, 0.0, 5.0])
        self.sentry_posts: list[tuple[np.ndarray, np.ndarray]] = []
        self._terrain: object | None = None  # Heightfield returned by add_terrain

        self._build_terrain()
        self._build_start_area()
        self._build_lava_lake()
        self._build_shuttle_gap()
        self._build_windmill_bridge()
        self._build_summit()
        self._build_goal()

    # ── terrain ──────────────────────────────────────────────────────────
    def _build_terrain(self) -> None:
        n, cell = 48, 2.0
        xs = np.linspace(0, 1, n)
        gx, gy = np.meshgrid(xs, xs, indexing="ij")
        h = (
            1.1 * np.sin(gx * 9.5) * np.cos(gy * 7.0)
            + 0.7 * np.sin(gx * 17 + 2.3) * np.sin(gy * 13 + 1.1)
            + 1.0
        )

        def dist(cx, cy):
            return np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)

        def bump(cx, cy, r, height):
            d = dist(cx, cy) / r
            return height * np.clip(1 - d * d, 0, 1) ** 2

        h += bump(0.10, 0.50, 0.16, 3.0)
        h -= bump(0.40, 0.50, 0.17, 4.5)
        h -= bump(0.63, 0.50, 0.10, 5.5)
        h += bump(0.88, 0.42, 0.16, 7.5)
        h += bump(0.88, 0.66, 0.10, 7.5)
        h = np.clip(h, -2.4, 9.0).astype(np.float32)
        self.heights = h

        self._terrain = self.world.add_terrain(
            heights=np.ascontiguousarray(h.T),
            cell_size=cell,
            origin=(-n * cell / 2, -n * cell / 2, 0),
            material=GRASS,
            friction=0.9,
            layer=f3d.CollisionLayer.TERRAIN,
        )

    def ground_height(self, x: float, y: float) -> float:
        """Bilinear height of the terrain surface at world (x, y).

        Used for placing objects during level construction and for enemies that
        need to hover above terrain (via direct height query rather than raycast).
        """
        n, cell = 48, 2.0
        fx = np.clip((x + n * cell / 2) / cell, 0.0, n - 1.001)
        fy = np.clip((y + n * cell / 2) / cell, 0.0, n - 1.001)
        i, j = int(fx), int(fy)
        u, v = fx - i, fy - j
        h = self.heights
        return float(
            h[i, j] * (1 - u) * (1 - v)
            + h[i + 1, j] * u * (1 - v)
            + h[i, j + 1] * (1 - u) * v
            + h[i + 1, j + 1] * u * v
        )

    # legacy alias
    def terrain_height(self, x: float, y: float) -> float:
        return self.ground_height(x, y)

    # ── helpers ──────────────────────────────────────────────────────────
    def _static(self, size, pos, mat=STONE, **kw) -> f3d.Body:
        return self.world.add_box(size=size, position=pos, static=True, material=mat, **kw)

    def _add_core(self, x: float, y: float, z: float) -> None:
        marker = self.world.add_box(
            size=(0.55, 0.55, 0.55),
            position=(x, y, z),
            static=True,
            material=GOLD,
            name=f"core_{len(self.cores)}",
        )
        marker.collision_mask = 0
        zone = self.world.add_trigger_zone(
            position=(x, y, z + 0.4), size=(2.2, 2.2, 3.4), name=f"core_zone_{len(self.cores)}"
        )
        self.cores.append(Core(marker=marker, zone=zone))

    def _add_checkpoint(self, x: float, y: float, z: float) -> None:
        flag = self.world.add_box(
            size=(0.18, 0.18, 2.4),
            position=(x, y, z + 1.2),
            static=True,
            material=CYAN,
            name=f"cp_flag_{len(self.checkpoints)}",
        )
        flag.collision_mask = 0
        zone = self.world.add_trigger_zone(
            position=(x, y, z + 1.0), size=(2.5, 2.5, 2.5), name=f"cp_{len(self.checkpoints)}"
        )
        self.checkpoints.append((zone, np.array([x, y, z + 1.2]), flag))

    def _add_lava(self, x, y, z, sx, sy) -> None:
        pool = self.world.add_box(
            size=(sx, sy, 0.25), position=(x, y, z), static=True, material=LAVA, name="lava_visual"
        )
        pool.collision_mask = 0
        zone = self.world.add_trigger_zone(
            position=(x, y, z + 0.6), size=(sx, sy, 2.8), name="lava"
        )
        self.lava_zones.append(zone)

    def _add_spring(self, x, y, z, launch=16.0) -> None:
        self._static((1.6, 1.6, 0.3), (x, y, z), STEEL, restitution=0.9)
        glow = self.world.add_box(
            size=(1.2, 1.2, 0.12),
            position=(x, y, z + 0.22),
            static=True,
            material=GREEN,
            name="spring_glow",
        )
        glow.collision_mask = 0
        zone = self.world.add_trigger_zone(
            position=(x, y, z + 0.8), size=(1.4, 1.4, 1.2), name="spring"
        )
        self.spring_pads.append((zone, launch))

    # ── zones ────────────────────────────────────────────────────────────
    def _build_start_area(self) -> None:
        x, y = -34.0, 0.0
        z = self.terrain_height(x, y)
        self.spawn = np.array([x, y, z + 1.6])
        self._static((4.5, 4.5, 0.6), (x, y, z + 0.2), DARKSTONE)
        self._add_checkpoint(x, y, z + 0.5)
        cx, cy = -22.0, 9.0
        self._add_core(cx, cy, self.terrain_height(cx, cy) + 1.4)
        for px, py in [(-28, -6), (-25, 5), (-30, 8)]:
            pz = self.terrain_height(px, py)
            self._static((1.0, 1.0, 2.4), (px, py, pz + 1.0), DARKSTONE)

    def _build_lava_lake(self) -> None:
        cx, cy = -9.6, 0.0
        self._add_lava(cx, cy, -1.0, 14.5, 13.0)
        stones = [
            (-17.2, -0.8, 0.35),
            (-13.8, 1.4, 0.8),
            (-9.8, 1.9, 1.1),
            (-5.8, 1.4, 0.9),
            (-2.4, 0.0, 0.4),
        ]
        for sx, sy, sz in stones:
            self._static((1.9, 1.9, 0.5), (sx, sy, sz), STONE)
        self._static((1.2, 1.2, 4.0), (-9.5, -1.6, 0.3), DARKSTONE)
        self._add_core(-9.5, -1.6, 3.1)
        ex, ey = 1.5, 0.0
        self._add_checkpoint(ex, ey, self.terrain_height(ex, ey) + 0.4)
        gz = self.terrain_height(4.0, 3.0)
        self.sentry_posts.append((np.array([4.0, 3.0, gz + 1.0]), np.array([4.0, -4.0, gz + 1.0])))

    def _build_shuttle_gap(self) -> None:
        self._add_lava(12.5, 0.0, -1.2, 10.0, 12.0)

        zw = self.terrain_height(7.2, 0.0) + 0.95
        ze = self.terrain_height(17.8, 0.0) + 0.55
        zs = max(zw, ze) + 0.35
        west = np.array([7.2, 0.0, zs])
        east = np.array([17.8, 0.0, zs])
        self._static((2.6, 2.6, 0.5), (7.2, 0.0, zw), STONE)
        self._static((2.6, 2.6, 0.5), (17.8, 0.0, ze), STONE)

        # Moving platforms via library API — no MovingPlatform boilerplate
        self.world.add_moving_platform(
            path=[west.tolist(), [12.5, 1.2, float(zs)]],
            period=5.2,
            size=(2.4, 2.4, 0.3),
            material=STEEL,
            name="shuttle_1",
            phase=0.0,
        )
        self.world.add_moving_platform(
            path=[[12.5, -1.2, float(zs)], east.tolist()],
            period=5.2,
            size=(2.4, 2.4, 0.3),
            material=STEEL,
            name="shuttle_2",
            phase=0.5,
        )
        self._add_core(12.5, 0.0, zs + 2.2)

    def _build_windmill_bridge(self) -> None:
        bx0, bx1, by = 20.0, 30.0, 0.0
        z = max(self.terrain_height(bx0, by), self.terrain_height(bx1, by)) + 0.4
        deck = self._static(((bx1 - bx0) + 2.5, 2.2, 0.4), ((bx0 + bx1) / 2, by, z), WOOD)
        self._static(
            (2.2, 2.2, 0.5), (bx0 - 1.6, by, self.terrain_height(bx0 - 1.6, by) + 0.55), STONE
        )
        hx = (bx0 + bx1) / 2
        mast = self._static((0.5, 0.5, 3.6), (hx, by + 1.6, z + 1.8), STEEL)
        hub = self._static((0.45, 0.45, 0.45), (hx, by + 1.1, z + 3.2), STEEL)
        for k, motor in ((0, 1.6), (1, -1.6)):
            blade = self.world.add_box(
                size=(5.2, 0.25, 0.3),
                position=(hx, by + 0.7 - 0.45 * k, z + 3.2),
                mass=6.0,
                material=RED if k == 0 else GOLD,
                name=f"blade_{k}",
            )
            self.world.ignore_collision(blade, hub)
            self.world.ignore_collision(blade, mast)
            self.world.ignore_collision(blade, deck)
            for other in self.windmill_blades:
                self.world.ignore_collision(blade, other)
            self.world.add_joint(
                "hinge",
                blade,
                hub,
                anchor_a=(0, 0, 0),
                anchor_b=(0, -0.4 - 0.45 * k, 0),
                axis=(0, 1, 0),
                motor_velocity=motor,
                motor_max_torque=4000.0,
            )
            self.windmill_blades.append(blade)
        self._add_checkpoint(bx1 + 2.0, by, z)

    def _build_summit(self) -> None:
        sx, sy = 36.0, -2.0
        self._add_spring(sx, sy, self.terrain_height(sx, sy) + 0.4, launch=19.0)
        px, py = 36.5, -7.5
        pz = self.terrain_height(px, py)
        self._add_core(px, py, pz + 1.4)
        self._add_core(px + 4.0, py + 3.0, self.terrain_height(px + 4.0, py + 3.0) + 1.4)
        self.sentry_posts.append(
            (np.array([px - 3.0, py - 3.0, pz + 1.0]), np.array([px + 5.0, py - 3.0, pz + 1.0]))
        )
        self.sentry_posts.append(
            (np.array([px + 5.0, py + 5.0, pz + 1.0]), np.array([px - 3.0, py + 5.0, pz + 1.0]))
        )
        self._add_checkpoint(px, py + 5.0, pz + 0.4)

    def _build_goal(self) -> None:
        gx, gy = 36.5, 14.0
        gz = self.terrain_height(gx, gy)
        for off in (-1.6, 1.6):
            self._static((0.6, 0.6, 4.2), (gx, gy + off, gz + 2.1), STEEL)
        self._static((0.6, 3.8, 0.6), (gx, gy, gz + 4.4), STEEL)
        self.goal_beam = self.world.add_box(
            size=(0.25, 3.0, 3.6),
            position=(gx, gy, gz + 2.0),
            static=True,
            material=RED,
            name="goal_beam",
        )
        self.goal_beam.collision_mask = 0
        self.goal_zone = self.world.add_trigger_zone(
            position=(gx, gy, gz + 1.8), size=(2.0, 3.0, 3.5), name="goal"
        )
        self.goal_zone.enabled = False

    # ── per-frame ────────────────────────────────────────────────────────
    def open_goal(self) -> None:
        self.goal_zone.enabled = True
        if self.goal_beam is not None:
            self.world.remove(self.goal_beam)
            self.goal_beam = None

    def update(self, t: float, dt: float) -> None:
        """Spin core markers."""
        for core in self.cores:
            if not core.collected:
                core.spin += 2.2 * dt
                half = math.cos(core.spin * 0.5)
                core.marker.set_orientation((half, 0.0, 0.0, math.sin(core.spin * 0.5)))
