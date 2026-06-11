# 빠른 시작

지금 바로 실행 가능한 15줄 예제 4개입니다.

---

## 1. 낙하하는 박스 (헤드리스 뷰어)

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=180)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()

print(f"박스 착지 위치 z = {box.position[2]:.3f} m")
```

**동작 설명:** 1 m 정육면체가 중력에 의해 낙하하여 지면에 착지합니다.
`Viewer`는 기본적으로 헤드리스(창 없음) 모드로 실행되며, `draw()` 호출마다
처리하거나 저장할 수 있는 `(H, W, 3)` uint8 ndarray를 반환합니다.

---

## 2. 앱 스타일 게임 루프 (창 있는 윈도우)

```python
import forge3d as f3d

app = f3d.App("물리 샌드박스", width=1280, height=720, fps=60)
ball = None

@app.on_start
def setup(world: f3d.World) -> None:
    global ball
    world.add_ground()
    ball = world.add_sphere(radius=0.4, position=(0, 0, 6),
                             material=f3d.Material(color="orange"))

@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 8))

app.run()
```

**동작 설명:** OS 창이 열립니다. **Space**를 누르면 공이 위로 튀어오릅니다.
`App`은 게임 루프, 월드, 뷰어, 입력을 자동으로 관리합니다.

---

## 3. 고화질 오프라인 비디오

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
world.add_sphere(
    radius=0.4, position=(0, 0, 4.4), mass=1.0, restitution=0.8,
    material=f3d.Material(color="orange"),
)
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(world, mode="hq", resolution=(1280, 720),
                   samples=16, output="bounce.mp4")
rec.run(duration=3.0, dt=1/240, fps=60)
```

**동작 설명:** 3초의 시뮬레이션이 forge3d의 NumPy 레이트레이서(GPU 불필요)로
풀 품질 오프라인 렌더링되어 `bounce.mp4`로 저장됩니다.
`samples=16`은 빠른 미리보기, `samples=64`는 영화 수준 품질입니다.

---

## 4. ECS (엔티티-컴포넌트 시스템)

```python
import forge3d as f3d

ew = f3d.EntityWorld()

# 모든 컴포넌트를 한 번에 포함한 동적 박스 엔티티 생성
e = ew.create_entity(
    f3d.Transform(position=[0, 0, 5]),
    f3d.Rigidbody(mass=1.0),
    f3d.MeshRenderer(shape="box", size=(1, 1, 1)),
)

# 물리 스텝
for _ in range(60):
    ew.step(dt=1/60)

tf = ew.get_component(e, f3d.Transform)
print(f"엔티티 z = {tf.position[2]:.3f}")
```

---

## 다음 단계

- [물리 튜토리얼](tutorials/01_physics.md) — 중력, 충돌, 마찰, 조인트, 레이캐스트
- [렌더링 튜토리얼](tutorials/02_rendering.md) — 카메라, 조명, 재질, HUD, 지형
- [로봇 튜토리얼](tutorials/03_robot.md) — UR5 FK/IK, 조인트 제어, 야코비안
- [RL 튜토리얼](tutorials/04_rl.md) — Gymnasium 환경, PPO 학습, JAX 배치 스텝
- [API 레퍼런스](../api/world.md) — 전체 클래스·메서드 문서 (영문)
