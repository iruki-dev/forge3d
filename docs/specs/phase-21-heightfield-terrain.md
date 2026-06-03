# Phase 21 SPEC — 지형 (Heightfield Terrain)

> Source of truth for P21. Only changes described here are permitted.

## 목표

2D 높이 배열로 정의된 **지형(heightfield)**을 정적 충돌 형상으로 지원한다.  
로봇 로코모션·야외 시뮬레이션에서 필수적이다.

### 참조
- **Bullet**: `btHeightfieldTerrainShape` — 2D 배열 + 높이 스케일
- **MuJoCo**: `hfield` geom — `nrow × ncol` float 배열
- **Godot**: `HeightMapShape3D` — `map_data` float array
- **Unity**: `TerrainCollider` + `TerrainData`

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `Heightfield` 데이터클래스 | `src/forge3d/collision/heightfield.py` (신규) |
| T2 | `World.add_terrain(heights, cell_size, ...)` 공개 API | `src/forge3d/facade.py` |
| T3 | 구 vs 높이맵 충돌 감지 | `src/forge3d/collision/detection.py` |
| T4 | 박스 vs 높이맵 충돌 감지 | `src/forge3d/collision/detection.py` |
| T5 | 높이맵 SceneSnapshot 렌더링 지원 (메시 변환) | `src/forge3d/render/snapshot.py` |
| T6 | 테스트 4종 | `tests/test_p21_terrain.py` (신규) |
| T7 | 예제: 언덕 지형 위 공 굴리기 | `examples/08_terrain.py` |

---

## Heightfield 데이터 구조

```python
@dataclass
class Heightfield:
    heights: np.ndarray   # shape (rows, cols), dtype float32
    cell_size: float      # 셀 한 변의 크기 (m)
    origin: np.ndarray    # (3,) 높이맵 원점 (world frame)
    # 파생 속성:
    @property
    def total_width(self) -> float: return self.cell_size * (self.cols - 1)
    @property
    def total_depth(self) -> float: return self.cell_size * (self.rows - 1)
```

---

## 충돌 감지 알고리즘 (구 vs 높이맵)

```
1. 구 중심을 높이맵 로컬 좌표로 변환
2. 셀 인덱스 계산: (i, j) = floor((x - origin_x) / cell_size)
3. 해당 셀 4꼭짓점에서 쌍선형 보간으로 높이 h = bilinear(heights, u, v)
4. depth = h + radius - sphere_z
5. depth > 0 → 충돌, normal = 셀 법선 (인접 높이 차에서 계산)
```

---

## 공개 API

```python
# 노이즈 기반 지형 생성
import numpy as np
rng = np.random.default_rng(42)
heights = rng.uniform(0, 2, (64, 64)).astype(np.float32)

terrain = world.add_terrain(
    heights=heights,
    cell_size=0.5,       # 32 m × 32 m 지형
    origin=(-16, -16, 0) # 중심 정렬
)

# 또는 이미지에서 불러오기 (grayscale PNG → float heights)
terrain = world.add_terrain_from_image("heightmap.png",
                                        cell_size=0.5, height_scale=5.0)
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 구가 높이맵 위에서 멈춤 (평탄 구역) | `test_sphere_rests_on_flat` |
| G2 | 구가 경사면에서 미끄러짐 | `test_sphere_slides_on_slope` |
| G3 | 박스가 높이맵 위에 안착 | `test_box_rests_on_terrain` |
| G4 | pytest + ruff + mypy 통과 | — |
