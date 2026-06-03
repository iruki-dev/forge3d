# Phase 19 SPEC — 충돌 레이어 & 마스크 필터링

> Source of truth for P19. Only changes described here are permitted.

## 목표

복잡한 씬에서 **어떤 물체가 어떤 물체와 충돌하는지 제어**한다.  
예: 플레이어 캐릭터는 적과 충돌하지만 아군 총알과는 충돌하지 않는다.

### 참조
- **Godot 4**: 32개 물리 레이어; `collision_layer` + `collision_mask`; 비트마스크
- **Unity**: 16개 레이어; Layer Collision Matrix; `Physics.IgnoreCollision(a, b)`
- **Bullet**: `setCollisionFilterMask` + `setCollisionFilterGroup`
- **Pymunk**: `ShapeFilter(group, mask, categories)`

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `CollisionLayer` 열거형 (32 비트) | `src/forge3d/collision/layers.py` (신규) |
| T2 | `_Body.collision_layer` + `_Body.collision_mask` 필드 | `src/forge3d/sim/world.py` |
| T3 | 브로드 페이즈 + 냅 스킵에서 레이어·마스크 검사 | `src/forge3d/collision/detection.py` |
| T4 | `World.ignore_collision(body_a, body_b)` 편의 함수 | `src/forge3d/facade.py` |
| T5 | `Body.collision_layer` / `Body.collision_mask` 프로퍼티 | `src/forge3d/facade.py` |
| T6 | 테스트 4종 | `tests/test_p19_layers.py` (신규) |

---

## 비트마스크 설계

```
레이어 번호: 0 ~ 31  (기본값: 레이어 0)
collision_layer: int  — 이 물체가 "속한" 레이어들 (비트 OR)
collision_mask:  int  — 이 물체가 "충돌 감지할" 레이어들 (비트 OR)

충돌 허용 조건: (A.collision_layer & B.collision_mask) != 0
             AND (B.collision_layer & A.collision_mask) != 0
```

기본값: `collision_layer = 0x0001`, `collision_mask = 0xFFFF` (모두와 충돌).

---

## 공개 API

```python
# 레이어 상수 정의 (사용자가 자유롭게)
LAYER_DEFAULT  = forge3d.CollisionLayer.DEFAULT  # 비트 0
LAYER_PLAYER   = 1 << 1
LAYER_ENEMY    = 1 << 2
LAYER_BULLET   = 1 << 3
LAYER_TRIGGER  = 1 << 4

player = world.add_sphere(radius=0.5, position=(0,0,1))
player.collision_layer = LAYER_PLAYER
player.collision_mask  = LAYER_DEFAULT | LAYER_ENEMY  # 바닥 + 적에만 반응

bullet = world.add_sphere(radius=0.05, mass=0.01)
bullet.collision_layer = LAYER_BULLET
bullet.collision_mask  = LAYER_DEFAULT | LAYER_ENEMY  # 바닥 + 적에만

# 두 물체 간 충돌 완전 무시 (편의 함수)
world.ignore_collision(player, friendly_npc)
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 레이어가 다른 두 물체 — 겹쳐도 충돌 없음 | `test_different_layers_no_collision` |
| G2 | 마스크 교차 물체 — 정상 충돌 | `test_matching_mask_collides` |
| G3 | `ignore_collision` — 특정 쌍만 무시 | `test_ignore_pair` |
| G4 | pytest + ruff + mypy 통과 | — |
