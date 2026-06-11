# v1 → v2 마이그레이션 가이드

> v1.x 코드를 v2.0으로 업그레이드하는 방법을 설명한다.  
> **v1 API는 v2에서 완전 하위 호환**된다 — 기존 코드는 수정 없이 동작한다.  
> v2 신기능을 활용하고 싶을 때만 아래 가이드를 따른다.

---

## 1. 설치

```bash
# v1
pip install pyforge3d==1.1.0

# v2 (Rust 확장 포함)
pip install pyforge3d==2.0.0
# 또는 소스에서: maturin build --release && pip install dist/pyforge3d-2.0.0-*.whl
```

Rust(`rustup`) 없이도 설치 가능하다 — Rust 빌드 실패 시 Python 폴백 자동 선택.

---

## 2. 버전 확인

```python
import forge3d
print(forge3d.__version__)  # "2.0.0"
```

---

## 3. 기존 코드 — 변경 불필요

v1의 모든 코드는 v2에서 그대로 동작한다.

```python
# v1 코드 — v2에서 수정 없이 동작
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=90)
while viewer.is_open:
    world.step(dt=1 / 60)
    viewer.draw()
```

---

## 4. v2 신기능 활용 — ECS

### v1 방식 (계속 지원)

```python
world = f3d.World()
box = world.add_box(size=(1,1,1), position=(0,0,5), mass=1.0)
```

### v2 ECS 방식 (선택)

```python
ew = f3d.EntityWorld()
box = ew.create_entity(
    f3d.Transform(position=[0, 0, 5]),
    f3d.MeshRenderer(mesh_id="box_1x1x1", material_id="red"),
    f3d.Rigidbody(mass=1.0),
)
ew.add_system(f3d.PhysicsSystem())
ew.add_system(f3d.RenderSystem())
ew.step(1/60)
```

### v1 Body → ECS 브릿지

```python
# 기존 v1 Body를 ECS 엔티티로 래핑
from forge3d import body_to_entity
entity = body_to_entity(world, v1_box, ew)
```

---

## 5. 모던 렌더링 파이프라인 (P26)

### v1 — OpenGL 3.3 Blinn-Phong

```python
viewer = f3d.Viewer(world, mode="realtime")
```

### v2 — 지연 PBR (자동 업그레이드)

```python
# Viewer는 내부적으로 DeferredRenderer 사용 (자동)
viewer = f3d.Viewer(world, mode="realtime")

# 직접 사용
from forge3d.render import DeferredRenderer
renderer = DeferredRenderer(width=1280, height=720)
frame = renderer.render(snapshot)
```

---

## 6. 오디오 시스템 (P28)

```python
# v2 신규
clip = f3d.AudioClip.from_sine(freq=440.0, duration=0.5)
audio_sys = f3d.AudioSystem()
audio_sys.play(clip, volume=0.8)

# 충돌 이벤트 → 사운드 트리거
handler = audio_sys.make_collision_handler(clip, max_volume=1.0)
world.on_collision_begin(handler)
```

---

## 7. 애니메이션 + IK (P29)

```python
# 골격 생성
skel = f3d.Skeleton.chain([
    np.array([0., 0., 0.]),
    np.array([0., 1., 0.]),
    np.array([0., 2., 0.]),
])

# FABRIK IK
solver = f3d.FABRIKSolver()
chain = [np.array([0., 0., 0.]), np.array([0., 1., 0.]), np.array([0., 2., 0.])]
solved = solver.solve(chain, target=np.array([1.5, 1.0, 0.]))
```

---

## 8. 파티클 시스템 (P31)

```python
ew = f3d.EntityWorld()
ew.create_entity(
    f3d.Transform(position=np.array([0., 5., 0.])),
    f3d.ParticleEmitter.preset("sparks", rate=500),
)
ps = f3d.ParticleSystem()
ew.add_system(ps)
ew.step(1/60)
print(f"{ps.total_alive} sparks alive")
```

---

## 9. 씬 저장/로드 (P30)

```python
# ECS 씬 저장
from forge3d import save_scene, load_scene
save_scene(ew, "my_scene.json")

# 씬 관리자 활용
mgr = f3d.SceneManager(ew)
mgr.on_scene_loaded(lambda: print("씬 로드됨"))
mgr.load_scene("level1.json")
```

---

## 10. Rust 코어 제어

```bash
# Rust 코어 비활성화 (Python 폴백)
USE_RUST_CORE=0 python my_game.py

# Rust 코어 강제 (없으면 오류)
USE_RUST_CORE=1 python my_game.py
```

```python
from forge3d.backend import USE_RUST_CORE
print("Rust 코어:", USE_RUST_CORE)
```

---

## 11. Breaking Changes

없음. v1 API는 동결됐다.

---

## 12. Deprecated

없음. v1 API는 v3까지 지원 보장.
