# 튜토리얼 2 — 실시간 & HQ 렌더링

forge3d는 동일한 API를 공유하는 두 가지 렌더러를 제공합니다: **실시간** OpenGL 래스터라이저와 **고화질** 소프트웨어 레이트레이서. 둘 다 `SceneSnapshot`을 소비하며 — 물리 코드는 변경할 필요가 없습니다.

---

## 실시간 뷰어

```python
import forge3d as f3d

world = f3d.World()
world.add_ground()
world.add_box(size=(1, 1, 1), position=(0, 0, 3), mass=1.0,
              material=f3d.Material(color="red"))

viewer = f3d.Viewer(world, width=1280, height=720)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()
```

### 뷰어 조작 (기본)

| 동작 | 조작 |
|------|------|
| 궤도 회전 | 왼쪽 드래그 |
| 이동 | 가운데 드래그 |
| 줌 | 스크롤 |
| 닫기 | Esc 또는 창 X |

---

## 카메라

```python
cam = f3d.OrbitCamera(
    target=(0, 0, 1),     # 바라보는 지점
    distance=10,           # 타겟까지 거리 (m)
    azimuth=45,            # 각도 (도)
    elevation=30,          # 수평 위 각도 (도)
    fov_deg=60,
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    inp = viewer.input
    # 오른쪽 드래그로 궤도 회전
    if inp.mouse_button(1):
        dx, dy = inp.mouse_delta()
        cam.rotate(d_azimuth=dx * 0.5, d_elevation=-dy * 0.5)
    cam.zoom(inp.scroll_delta() * 0.1)
    viewer.set_camera(cam.to_snapshot())
    world.step()
    viewer.draw()
```

### 팔로우 카메라

```python
# frame="world" (기본): 오프셋이 월드 기준으로 유지됨
cam = f3d.FollowCamera(car, offset=(0, -8, 4))

# frame="local": 오프셋이 차체와 함께 회전
cam = f3d.FollowCamera(car, offset=(-8, 0, 3), frame="local", smoothing_hz=8)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))  # dt 보정 스무딩
    viewer.draw()
```

---

## 재질

```python
# 기본 색상 재질
red_mat   = f3d.Material(color="red")
blue_mat  = f3d.Material(color=(0.2, 0.4, 1.0))   # RGB 0–1

# PBR 파라미터
pbr_mat = f3d.Material(
    color=(0.8, 0.6, 0.2),
    roughness=0.3,     # 0 = 거울, 1 = 완전 확산
    metallic=0.9,      # 0 = 비금속, 1 = 금속
    emissive=2.5,      # 발광 강도 (v2.1+)
)

# 사전 정의된 이름
f3d.Material(color="ground")    # 갈색 지면
f3d.Material(color="default")   # 연한 회색
f3d.Material(color="orange")
```

---

## 조명 & 그림자

```python
viewer = f3d.Viewer(
    world,
    shadow_resolution=2048,   # 기본값: 1024 (v2.1에서 512→1024로 상향)
)
```

기본 조명:
- 방향광 (위에서 약간 앞쪽)
- 앰비언트 강도 0.3
- PCF 소프트 그림자

---

## 지형 렌더링

```python
import numpy as np

heights = (np.sin(np.linspace(0, 4*np.pi, 64))[:, None] *
           np.cos(np.linspace(0, 3*np.pi, 64))[None, :] * 3
          ).astype(np.float32)

world.add_terrain(
    heights=np.clip(heights - heights.min(), 0, 8),
    cell_size=2.0,
    origin=(-64, -64, 0),
    material=f3d.Material(color=(0.28, 0.42, 0.16), roughness=0.95),
    friction=0.9,
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    world.step()
    viewer.draw()   # 지형이 그림자가 있는 쉐이딩된 메시로 표시됨
```

---

## HUD 텍스트 오버레이

```python
while viewer.is_open:
    world.step()
    viewer.draw()   # 3D 씬

    viewer.draw_text(f"★ {stars}/20", x=10, y=10, size=28,
                     color=(1.0, 0.9, 0.1))
    viewer.draw_text("게임 오버", x=640, y=360,
                     size=64, anchor="center")
    viewer.draw_text("ESC로 종료", x=1270, y=10,
                     size=18, anchor="topright")
```

앵커 옵션: `"topleft"` (기본값), `"center"`, `"topright"`.

---

## 고화질 레이트레이서

```python
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(
    world,
    mode="hq",
    resolution=(1920, 1080),
    samples=64,         # 64 = 영화 수준, 16 = 미리보기
    output="scene.mp4",
)
rec.run(duration=3.0, dt=1/240, fps=60)
```

PNG 시퀀스 저장:

```python
rec = f3d.Recorder(world, mode="hq", output="frames/frame_{:04d}.png")
rec.run(duration=2.0)
```

---

## 지연 렌더러 (v2.0+, 고급)

```python
from forge3d.render import DeferredRenderer

renderer = DeferredRenderer(width=1280, height=720)
snap = world.snapshot()
frame = renderer.render(snap)   # (720, 1280, 3) uint8
```

지연 렌더러는 다음을 지원합니다:
- G-버퍼 (위치, 법선, 알베도, 발광)
- Cascaded Shadow Maps (CSM) 4 캐스케이드
- SSAO (64샘플)
- HDR 프레임버퍼 + ACES 톤매핑
- Kawase 블룸

---

## App 스타일 렌더링

```python
app = f3d.App("데모", width=1280, height=720)

@app.on_render
def render(viewer: f3d.Viewer) -> None:
    viewer.draw_text(f"FPS: {1/viewer.dt:.0f}", x=10, y=10, size=20)

app.run()
```

---

## 다음: [로봇 튜토리얼](03_robot.md)
