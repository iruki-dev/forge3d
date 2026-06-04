# SPEC: Phase 31 — 파티클 시스템 (GPU 컴퓨트 + JAX vmap)

> 파생: `docs/ROADMAP_v2.md` P31. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

GPU 컴퓨트 셰이더(GLSL 4.3) + JAX vmap 병렬화로 **10만 파티클을 60FPS**로 처리하는 이미터·수명·물리 반응 파티클 시스템을 제공한다.

---

## 2. 범위

### 포함

- **ParticleEmitter** ECS 컴포넌트: 생성율, 초기 속도·방향 분포, 수명
- **Particle 상태 버퍼**: 위치·속도·수명·색상 — SSBO 또는 NumPy/JAX 배열
- **GPU 컴퓨트 패스** (GLSL `update_particles.comp`): 속도 통합, 수명 감소
- **JAX vmap 경로**: GPU 컴퓨트 불가 환경 폴백
- **물리 반응**: 파티클-지면 충돌, 반발계수
- **VFX 프리셋**: smoke, sparks, debris, rain

### 제외 (Out of scope)

- 파티클 간 상호작용 (SPH 유체) — v2.2 이후
- 서브 이미터 (파티클이 파티클을 생성) — v2.2 이후
- 렌더: 빌보드(스프라이트) 렌더링 (P26 지연 파이프라인과 통합)

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/particle/__init__.py` | 공개 파티클 API |
| `src/forge3d/particle/emitter.py` | `ParticleEmitter` 컴포넌트 |
| `src/forge3d/particle/system.py` | `ParticleSystem` (GPU/CPU 경로 선택) |
| `src/forge3d/particle/presets.py` | VFX 프리셋 팩토리 |
| `src/forge3d/render/shaders/update_particles.comp` | GLSL 컴퓨트 셰이더 |
| `tests/test_p31_particle.py` | CPU 경로 단위 테스트 |

### 핵심 인터페이스

```python
@dataclass
class ParticleEmitter(Component):
    rate: float = 100.0          # 파티클/초
    lifetime: float = 2.0        # 수명(초)
    initial_speed: float = 5.0
    spread_angle: float = 30.0   # 도
    gravity: float = -9.81
    restitution: float = 0.3
    max_particles: int = 10000

# VFX 프리셋
sparks = ParticleEmitter.preset("sparks", rate=500, lifetime=0.5, initial_speed=8.0)
smoke  = ParticleEmitter.preset("smoke",  rate=50,  lifetime=3.0, initial_speed=1.0)
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. 파티클 버퍼 + JAX vmap 업데이터** — 완료 조건: 10만 파티클 CPU 업데이트 < 16ms
- [ ] **T2. ParticleEmitter 컴포넌트** — 완료 조건: `rate` 파티클/초 생성 확인
- [ ] **T3. GPU 컴퓨트 셰이더** — 완료 조건: GL4.3 SSBO 읽기/쓰기, 위치 갱신
- [ ] **T4. 지면 충돌** — 완료 조건: y=0에서 반발계수 바운스
- [ ] **T5. VFX 프리셋** — 완료 조건: smoke/sparks 프리셋 시각 확인
- [ ] **T6. 테스트** — 완료 조건: 6개 테스트 PASS (CPU 경로)

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 10만 파티클 JAX vmap 업데이트 < 33ms (30FPS 이상) | `test_p31_particle::test_performance` |
| G2 | 수명 만료 후 파티클 재활용(풀링) | `test_p31_particle::test_particle_pool` |
| G3 | 지면 충돌 반발 속도 부호 반전 | `test_p31_particle::test_ground_bounce` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
