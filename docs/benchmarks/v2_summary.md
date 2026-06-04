# forge3d v2.0.0 — 전체 벤치마크 리포트

> 환경: Python 3.12 / Rust 1.96 / Mesa Intel UHD 620 / Linux x86_64  
> 빌드: maturin dev profile (release 시 추가 향상 예상)  
> 측정: 각 항목 50~100회 평균

---

## 1. P25 — Rust 네이티브 확장 (BVH 광역단계)

| 바디 수 N | Rust BVH (ms) | Python O(N²) (ms) | 속도 향상 |
|----------|--------------|------------------|---------|
| 100      | 0.39         | 5.53             | **14×** |
| 500      | 2.79         | 115.40           | **41×** |
| 1000     | 6.36         | 472.34           | **74×** |

> **목표 G4: ≥10× → 달성** (dev build 기준)  
> Release build (`maturin build --release`) 시 추가 2~3× 향상 예상.

### GJK 충돌 감지 (dev build)

| 지표 | 값 |
|------|-----|
| 3000 GJK 호출 | 143.6 ms |
| 호출당 평균 | ~48 µs |

### PGS 접촉 솔버 (C=500 접촉)

| 지표 | 값 |
|------|-----|
| 6 반복 / 호출 (dev) | ~4.4 ms |

---

## 2. P26 — 지연 PBR 렌더링

> Mesa llvmpipe 소프트웨어 래스터라이저 기준 (실제 GPU ≫ 빠름)

| 씬 복잡도 | FPS (Xvfb, 640×480) |
|---------|---------------------|
| 200 오브젝트 | 측정 환경 의존 (소프트 GL) |

**파이프라인:**
1. Shadow Pass — CSM 2 cascade (2048×2048)
2. G-Buffer Pass — 위치/법선/알베도-roughness/emissive-metallic
3. SSAO — 64샘플 반구 AO + 5×5 blur
4. Lighting — GGX PBR + PCF 그림자
5. Bloom — Kawase 다운/업샘플
6. Tonemap — ACES Filmic + γ2.2

---

## 3. P27 — ECS 쿼리 처리량

| 씬 규모 | `query(Transform, Rigidbody)` |
|--------|-------------------------------|
| 1,000 엔티티 | **0.74 ms/call** |

> Python dict 교집합 기반. 핫루프에서는 결과 캐싱 권장.

---

## 4. P28 — 오디오 시스템

| 항목 | 결과 |
|-----|------|
| AudioClip 로드 (WAV, 44100 Hz) | < 1ms |
| NullDriver play_at() | < 0.01ms |
| OpenAL 헤드리스 환경 | NullDriver 자동 폴백 |

---

## 5. P29 — FABRIK IK 솔버

| 링크 수 | 목표 거리 | 수렴 반복 | 끝단 오차 |
|--------|---------|---------|---------|
| 3      | 1.5m    | ≤ 20   | < 1e-4m |
| 6      | 2.5m    | ≤ 30   | < 1e-4m |

---

## 6. P31 — 파티클 시스템

| 파티클 수 | NumPy 벡터화 (ms/frame) | 목표 |
|---------|----------------------|------|
| 10만    | **16.4 ms**          | < 33ms (30FPS) ✅ |

> JAX vmap 경로 (`ENGINE_BACKEND=jax`) 추가 향상 가능.

---

## 7. 전체 테스트 현황

| 카테고리 | 테스트 수 |
|--------|---------|
| P0~P24 (v1 코어) | 459 |
| P25 Rust Core | 15 |
| P26 DeferredRenderer | 10 |
| P27 ECS | 17 |
| P28 Audio | 12 |
| P29 Animation+IK | 16 |
| P30 Scene Mgmt | 11 |
| P31 Particle | 10 |
| P32 UI | 16 |
| P33 Editor | 17 |
| P34 wgpu (별도) | 7 |
| **총계** | **590** |

---

## 결론

- **물리 핫루프**: Rust 확장으로 BVH N=1000에서 **74× 향상**
- **렌더링**: 지연 PBR + SSAO + HDR + Bloom — 현대적 파이프라인
- **파티클**: 10만 개를 16ms/frame (NumPy 벡터화)
- **v1 호환**: 590 tests PASS, v1 예제 수정 없이 동작
