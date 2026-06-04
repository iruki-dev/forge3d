# SPEC: Phase 28 — 오디오 시스템 (3D 공간음)

> 파생: `docs/ROADMAP_v2.md` P28. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

OpenAL 기반 3D 공간 오디오 시스템을 구현하여 물리 충돌 이벤트와 ECS 컴포넌트에서 사운드를 트리거할 수 있게 한다.

---

## 2. 범위

### 포함

- **AudioClip**: WAV/OGG 파일 로드 (`soundfile` 또는 `pydub`)
- **AudioSource** 컴포넌트: 3D 위치, 감쇠, 루프, 볼륨, 피치
- **AudioListener** 컴포넌트: 카메라에 부착, 월드 청취 위치
- **AudioSystem**: ECS 시스템, OpenAL 컨텍스트 관리
- **충돌 이벤트 연동**: `on_collision_begin` → 충돌음 트리거
- **null 오디오 드라이버**: 헤드리스 환경 폴백 (no-op 구현)

### 제외 (Out of scope)

- HRTF(Head-Related Transfer Function) — v2.1 이후
- 오디오 믹서 / 이펙트 체인 (리버브, 이퀄라이저) — v2.1 이후
- 음악 스트리밍 — v2.1 이후

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/audio/__init__.py` | 공개 오디오 API |
| `src/forge3d/audio/clip.py` | `AudioClip` — 파일 로드 + PCM 버퍼 |
| `src/forge3d/audio/source.py` | `AudioSource` ECS 컴포넌트 |
| `src/forge3d/audio/listener.py` | `AudioListener` ECS 컴포넌트 |
| `src/forge3d/audio/system.py` | `AudioSystem` — OpenAL 컨텍스트, 재생 관리 |
| `src/forge3d/audio/null_driver.py` | 헤드리스 no-op 드라이버 |
| `tests/test_p28_audio.py` | null 드라이버 기반 단위 테스트 |

### 핵심 인터페이스

```python
@dataclass
class AudioSource(Component):
    clip: AudioClip
    volume: float = 1.0
    pitch: float = 1.0
    loop: bool = False
    min_distance: float = 1.0    # 감쇠 시작 거리
    max_distance: float = 50.0   # 감쇠 최대 거리
    auto_play: bool = False

class AudioSystem(System):
    def update(self, ew: EntityWorld, dt: float) -> None: ...

# 충돌 이벤트 연동
world.on_collision_begin(lambda e: audio_system.play_at(
    clip=impact_clip, position=e.point, volume=min(1.0, e.impulse / 10)
))
```

### 의존성

```toml
# pyproject.toml dependencies 추가
"soundfile>=0.12"   # WAV/OGG 로드
"openal-python>=0.7"  # PyOpenAL (없으면 null 드라이버)
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. null 드라이버 + AudioClip** — 완료 조건: `AudioClip.load()` WAV 파일 → PCM 배열
- [ ] **T2. AudioSource/Listener 컴포넌트** — 완료 조건: ECS `add_component` 동작
- [ ] **T3. AudioSystem (null 드라이버)** — 완료 조건: 헤드리스에서 예외 없이 `update()` 실행
- [ ] **T4. OpenAL 백엔드** — 완료 조건: OpenAL 가용 시 3D 감쇠 재생 (거리별 볼륨 측정)
- [ ] **T5. 충돌 이벤트 연동** — 완료 조건: 충돌 시 `on_collision_begin` 콜백으로 사운드 트리거
- [ ] **T6. 테스트** — 완료 조건: null 드라이버 기준 7개 테스트 PASS

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `AudioClip.load("test.wav")` PCM 배열 반환 | `tests/test_p28_audio.py::test_clip_load` |
| G2 | null 드라이버로 `AudioSystem.update()` 예외 없음 | `tests/test_p28_audio.py::test_null_driver` |
| G3 | 충돌 이벤트 → `play_at()` 호출 횟수 일치 | `tests/test_p28_audio.py::test_collision_trigger` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
