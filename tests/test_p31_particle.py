"""P31 — 파티클 시스템 검증 테스트.

게이트:
  G1: 10만 파티클 vmap 업데이트 < 33ms (NumPy CPU)
  G2: 수명 만료 후 파티클 재활용 (풀링)
  G3: 지면 충돌 반발 속도 부호 반전
  G4: 전체 기존 테스트 회귀 없음
"""
from __future__ import annotations

import time

import numpy as np
import pytest

import forge3d as f3d
from forge3d.particle.system import _N_COLS, _ALIVE, _PY, _VY, ParticleState


# ── 파티클 이미터 기본 ────────────────────────────────────────────────────────

def test_emitter_preset_sparks():
    """sparks 프리셋이 올바른 속성을 갖는다."""
    from forge3d.particle.presets import sparks
    e = sparks()
    assert e.rate == 500
    assert e.lifetime == 0.5
    assert e.initial_speed == 8.0


def test_emitter_preset_smoke():
    """smoke 프리셋 속성 확인."""
    from forge3d.particle.presets import smoke
    e = smoke()
    assert e.rate == 50
    assert e.lifetime == 3.0
    assert abs(e.gravity) < 1.0  # 연기는 약한 중력


def test_emitter_all_presets():
    """4개 프리셋 모두 생성 가능."""
    for name in ("sparks", "smoke", "debris", "rain"):
        e = f3d.ParticleEmitter.preset(name)
        assert isinstance(e, f3d.ParticleEmitter)
        assert e.max_particles > 0


# ── G2: 파티클 생성 + 풀링 ───────────────────────────────────────────────────

def test_particle_pool_reuse():
    """G2: 수명 만료 후 파티클이 재활용된다."""
    emitter = f3d.ParticleEmitter(
        rate=1000, lifetime=0.05, initial_speed=1.0,
        gravity=0.0, max_particles=100,
    )
    state = ParticleState(emitter, seed=0)
    origin = np.zeros(3, dtype=np.float32)

    # 짧은 수명이라 많이 생성 후 모두 만료
    for _ in range(10):
        state.step(origin, dt=0.01)

    # 만료 후 계속 step하면 새로 생성
    for _ in range(5):
        state.step(origin, dt=0.01)

    # 풀 내 일부가 다시 활성화돼야 함
    assert state.alive_count > 0


def test_particle_rate_controls_spawn():
    """rate가 클수록 dt 내 더 많은 파티클이 생성된다."""
    origin = np.zeros(3, dtype=np.float32)

    emitter_fast = f3d.ParticleEmitter(rate=1000, lifetime=5.0, max_particles=500)
    state_fast = ParticleState(emitter_fast, seed=1)

    emitter_slow = f3d.ParticleEmitter(rate=10, lifetime=5.0, max_particles=500)
    state_slow = ParticleState(emitter_slow, seed=1)

    for _ in range(5):
        state_fast.step(origin, dt=0.1)
        state_slow.step(origin, dt=0.1)

    assert state_fast.alive_count > state_slow.alive_count


# ── G3: 지면 충돌 ────────────────────────────────────────────────────────────

def test_ground_bounce():
    """G3: y=0 지면에서 반발계수 바운스 — vy 부호 반전."""
    emitter = f3d.ParticleEmitter(
        rate=0, lifetime=10.0, initial_speed=0.0,
        gravity=-9.81, restitution=0.5, ground_y=0.0, max_particles=10,
    )
    state = ParticleState(emitter, seed=0)

    # 수동으로 파티클 하나 설정: y=0.1, vy=-5 (아래로 낙하)
    state.buf[0, :] = [0., 0.1, 0.,  0., -5., 0.,  0., 10., 1., 0.]
    state.step(np.zeros(3), dt=0.05)

    # y가 ground_y 이상이어야 함
    assert state.buf[0, _PY] >= 0.0

    # vy가 양수로 반전되어야 함 (반발)
    assert state.buf[0, _VY] > 0.0


def test_ground_restitution_magnitude():
    """반발계수 0.5이면 vy가 반절로 줄어든다."""
    emitter = f3d.ParticleEmitter(
        rate=0, lifetime=10.0, gravity=0.0, restitution=0.5,
        ground_y=0.0, max_particles=5,
    )
    state = ParticleState(emitter, seed=0)
    state.buf[0, :] = [0., -0.01, 0.,  0., -4.0, 0.,  0., 10., 1., 0.]
    state.step(np.zeros(3), dt=0.001)

    # vy ≈ 4.0 * 0.5 = 2.0 (중력 없으므로)
    assert abs(state.buf[0, _VY] - 2.0) < 0.5


# ── G1: 성능 벤치마크 ────────────────────────────────────────────────────────

def test_performance_100k():
    """G1: 10만 파티클 NumPy 업데이트 < 33ms."""
    emitter = f3d.ParticleEmitter(
        rate=0, lifetime=10.0, gravity=-9.81,
        restitution=0.3, max_particles=100_000,
    )
    state = ParticleState(emitter, seed=42)
    origin = np.zeros(3, dtype=np.float32)

    # 모든 파티클 활성화
    state.buf[:, _ALIVE] = 1.0
    state.buf[:, 3] = np.random.randn(100_000).astype(np.float32)  # vx
    state.buf[:, 4] = np.random.randn(100_000).astype(np.float32)  # vy
    state.buf[:, 6] = 0.0   # age
    state.buf[:, 7] = 10.0  # lifetime

    N = 5
    t0 = time.perf_counter()
    for _ in range(N):
        state.step(origin, dt=1 / 60)
    elapsed_ms = (time.perf_counter() - t0) / N * 1000

    print(f"\n[G1] 10만 파티클 NumPy 업데이트: {elapsed_ms:.1f}ms/frame")
    assert elapsed_ms < 33.0, f"성능 기준 미달: {elapsed_ms:.1f}ms (목표 < 33ms)"


# ── ECS 연동 ─────────────────────────────────────────────────────────────────

def test_particle_system_ecs():
    """ParticleSystem이 ECS에서 파티클 상태를 업데이트한다."""
    ew = f3d.EntityWorld()
    emitter = f3d.ParticleEmitter(rate=100, lifetime=2.0, max_particles=200)
    ew.create_entity(
        f3d.Transform(position=np.array([0., 5., 0.])),
        emitter,
    )
    ps = f3d.ParticleSystem()
    ew.add_system(ps)

    for _ in range(10):
        ew.step(1 / 60)

    assert ps.total_alive > 0, "파티클이 생성되지 않음"


def test_particle_inactive_emitter():
    """active=False 이미터는 파티클을 생성하지 않는다."""
    ew = f3d.EntityWorld()
    emitter = f3d.ParticleEmitter(rate=100, lifetime=2.0, max_particles=200, active=False)
    ew.create_entity(f3d.Transform(), emitter)
    ps = f3d.ParticleSystem()
    ew.add_system(ps)
    for _ in range(20):
        ew.step(1 / 60)
    assert ps.total_alive == 0
