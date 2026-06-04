"""ParticleSystem — GPU 컴퓨트 or JAX vmap 파티클 업데이터.

파티클 상태 버퍼 레이아웃 (N, 10) float32:
  [0:3]  position (x,y,z)
  [3:6]  velocity (vx,vy,vz)
  [6]    age       (초)
  [7]    lifetime  (초)
  [8]    alive     (1.0=활성, 0.0=비활성)
  [9]    _pad      (정렬용)
"""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.system import System
from forge3d.ecs.transform import Transform
from forge3d.particle.emitter import ParticleEmitter

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld

# 파티클 버퍼 열 인덱스
_PX, _PY, _PZ = 0, 1, 2
_VX, _VY, _VZ = 3, 4, 5
_AGE, _LIFE, _ALIVE, _PAD = 6, 7, 8, 9
_N_COLS = 10

_USE_JAX = os.environ.get("ENGINE_BACKEND", "numpy") == "jax"


def _update_particles_numpy(
    buf: np.ndarray,
    emitter: "ParticleEmitter",
    origin: np.ndarray,
    dt: float,
    rng: np.random.Generator,
    n_spawn: int,
) -> np.ndarray:
    """NumPy 벡터화 파티클 업데이터."""
    buf = buf.copy()
    alive_mask = buf[:, _ALIVE] > 0.5

    # 속도 + 중력 적용
    buf[alive_mask, _VY] += emitter.gravity * dt
    buf[alive_mask, _PX] += buf[alive_mask, _VX] * dt
    buf[alive_mask, _PY] += buf[alive_mask, _VY] * dt
    buf[alive_mask, _PZ] += buf[alive_mask, _VZ] * dt

    # 수명 감소
    buf[alive_mask, _AGE] += dt

    # 지면 충돌 (y=ground_y)
    ground = emitter.ground_y
    hit_ground = alive_mask & (buf[:, _PY] < ground)
    buf[hit_ground, _PY] = ground
    buf[hit_ground, _VY] = -buf[hit_ground, _VY] * emitter.restitution

    # 수명 만료 → 재활용
    expired = alive_mask & (buf[:, _AGE] >= buf[:, _LIFE])
    buf[expired, _ALIVE] = 0.0

    # 새 파티클 생성
    if n_spawn > 0:
        dead_indices = np.where(buf[:, _ALIVE] < 0.5)[0][:n_spawn]
        if len(dead_indices) > 0:
            spread_rad = np.radians(emitter.spread_angle)
            theta = rng.uniform(0, 2 * np.pi, len(dead_indices))
            phi = rng.uniform(0, spread_rad, len(dead_indices))
            speed = emitter.initial_speed

            vx = speed * np.sin(phi) * np.cos(theta)
            vy = speed * np.cos(phi)
            vz = speed * np.sin(phi) * np.sin(theta)

            buf[dead_indices, _PX] = origin[0]
            buf[dead_indices, _PY] = origin[1]
            buf[dead_indices, _PZ] = origin[2]
            buf[dead_indices, _VX] = vx
            buf[dead_indices, _VY] = vy
            buf[dead_indices, _VZ] = vz
            buf[dead_indices, _AGE] = 0.0
            buf[dead_indices, _LIFE] = emitter.lifetime
            buf[dead_indices, _ALIVE] = 1.0

    return buf


def _update_particles_jax(
    buf: np.ndarray,
    emitter: "ParticleEmitter",
    origin: np.ndarray,
    dt: float,
    rng: np.random.Generator,
    n_spawn: int,
) -> np.ndarray:
    """JAX vmap 파티클 업데이터 (ENGINE_BACKEND=jax 시 사용)."""
    try:
        import jax
        import jax.numpy as jnp

        jax.config.update("jax_enable_x64", False)
        buf_j = jnp.array(buf)
        alive = buf_j[:, _ALIVE] > 0.5

        # 벡터화 업데이트
        vy_new = jnp.where(alive, buf_j[:, _VY] + emitter.gravity * dt, buf_j[:, _VY])
        py_new = jnp.where(alive, buf_j[:, _PY] + vy_new * dt, buf_j[:, _PY])
        px_new = jnp.where(alive, buf_j[:, _PX] + buf_j[:, _VX] * dt, buf_j[:, _PX])
        pz_new = jnp.where(alive, buf_j[:, _PZ] + buf_j[:, _VZ] * dt, buf_j[:, _PZ])
        age_new = jnp.where(alive, buf_j[:, _AGE] + dt, buf_j[:, _AGE])

        # 지면 충돌
        hit = alive & (py_new < emitter.ground_y)
        py_new = jnp.where(hit, emitter.ground_y, py_new)
        vy_new = jnp.where(hit, -vy_new * emitter.restitution, vy_new)

        # 수명 만료
        expired = alive & (age_new >= buf_j[:, _LIFE])
        alive_new = jnp.where(expired, 0.0, buf_j[:, _ALIVE])

        buf_j = buf_j.at[:, _PX].set(px_new)
        buf_j = buf_j.at[:, _PY].set(py_new)
        buf_j = buf_j.at[:, _PZ].set(pz_new)
        buf_j = buf_j.at[:, _VY].set(vy_new)
        buf_j = buf_j.at[:, _AGE].set(age_new)
        buf_j = buf_j.at[:, _ALIVE].set(alive_new)

        buf = np.array(buf_j)
    except Exception:
        buf = _update_particles_numpy(buf, emitter, origin, dt, rng, 0)
        n_spawn = n_spawn  # 생성은 numpy로

    # 새 파티클 생성은 numpy로 (JAX random API 복잡도 회피)
    if n_spawn > 0:
        dead_indices = np.where(buf[:, _ALIVE] < 0.5)[0][:n_spawn]
        if len(dead_indices) > 0:
            spread_rad = np.radians(emitter.spread_angle)
            theta = rng.uniform(0, 2 * np.pi, len(dead_indices))
            phi = rng.uniform(0, spread_rad, len(dead_indices))
            speed = emitter.initial_speed
            buf[dead_indices, _PX] = origin[0]
            buf[dead_indices, _PY] = origin[1]
            buf[dead_indices, _PZ] = origin[2]
            buf[dead_indices, _VX] = speed * np.sin(phi) * np.cos(theta)
            buf[dead_indices, _VY] = speed * np.cos(phi)
            buf[dead_indices, _VZ] = speed * np.sin(phi) * np.sin(theta)
            buf[dead_indices, _AGE] = 0.0
            buf[dead_indices, _LIFE] = emitter.lifetime
            buf[dead_indices, _ALIVE] = 1.0

    return buf


class ParticleState:
    """단일 이미터의 파티클 풀 상태."""

    def __init__(self, emitter: ParticleEmitter, seed: int = 0) -> None:
        self.emitter = emitter
        self.buf = np.zeros((emitter.max_particles, _N_COLS), dtype=np.float32)
        self.rng = np.random.default_rng(seed)
        self._spawn_accum: float = 0.0

    def step(self, origin: np.ndarray, dt: float) -> None:
        """파티클 상태를 dt 만큼 전진시킨다."""
        if not self.emitter.active:
            return

        self._spawn_accum += self.emitter.rate * dt
        n_spawn = int(self._spawn_accum)
        self._spawn_accum -= n_spawn

        updater = _update_particles_jax if _USE_JAX else _update_particles_numpy
        self.buf = updater(
            self.buf, self.emitter, np.asarray(origin, dtype=np.float32),
            dt, self.rng, n_spawn,
        )

    @property
    def alive_positions(self) -> np.ndarray:
        """살아있는 파티클 위치 (K, 3) float32."""
        mask = self.buf[:, _ALIVE] > 0.5
        return self.buf[mask, :3]

    @property
    def alive_count(self) -> int:
        return int((self.buf[:, _ALIVE] > 0.5).sum())

    @property
    def pool_size(self) -> int:
        return self.emitter.max_particles


class ParticleSystem(System):
    """ECS 시스템 — ParticleEmitter 엔티티를 순회해 파티클 상태를 업데이트한다."""

    def __init__(self) -> None:
        self._states: dict[int, ParticleState] = {}

    def update(self, ew: "EntityWorld", dt: float) -> None:
        for e, tf, emitter in ew.query(Transform, ParticleEmitter):
            entity = int(e)
            transform: Transform = tf  # type: ignore[assignment]
            em: ParticleEmitter = emitter  # type: ignore[assignment]
            if entity not in self._states:
                self._states[entity] = ParticleState(em)
            self._states[entity].step(transform.position, dt)

    def get_state(self, entity: int) -> ParticleState | None:
        return self._states.get(entity)

    @property
    def total_alive(self) -> int:
        return sum(s.alive_count for s in self._states.values())
