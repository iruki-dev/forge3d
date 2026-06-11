"""P28 — 오디오 시스템 검증 테스트.

게이트:
  G1: AudioClip 생성 및 PCM 배열 반환
  G2: null 드라이버로 AudioSystem.update() 예외 없음
  G3: 충돌 이벤트 → play_at() 호출 횟수 일치
  G4: 전체 기존 테스트 회귀 없음
"""
from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

import forge3d as f3d


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _make_wav(path: Path, freq: float = 440.0, duration: float = 0.1, sr: int = 44100) -> None:
    """테스트용 WAV 파일 생성."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    samples = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


# ── G1: AudioClip ─────────────────────────────────────────────────────────────

def test_clip_from_sine():
    """G1a: AudioClip.from_sine()이 float32 PCM 배열을 반환한다."""
    clip = f3d.AudioClip.from_sine(freq=440.0, duration=0.1, sample_rate=44100)
    assert clip.samples.dtype == np.float32
    assert len(clip.samples) == pytest.approx(4410, abs=1)
    assert -1.0 <= clip.samples.min() and clip.samples.max() <= 1.0
    assert clip.channels == 1
    assert clip.sample_rate == 44100


def test_clip_duration():
    """G1b: duration 프로퍼티가 올바른 값을 반환한다."""
    clip = f3d.AudioClip.from_sine(freq=440.0, duration=0.5)
    assert abs(clip.duration - 0.5) < 0.01


def test_clip_to_pcm16():
    """G1c: to_pcm16()이 bytes를 반환하고 크기가 맞다."""
    clip = f3d.AudioClip.from_sine(duration=0.1, sample_rate=44100)
    pcm = clip.to_pcm16()
    assert isinstance(pcm, bytes)
    assert len(pcm) == len(clip.samples) * 2  # 2 bytes per sample


def test_clip_load_wav():
    """G1d: WAV 파일에서 AudioClip을 로드한다."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = Path(f.name)
    _make_wav(path)

    clip = f3d.AudioClip.load(path)
    assert clip.samples.dtype == np.float32
    assert clip.sample_rate == 44100
    assert clip.channels == 1
    assert clip.duration > 0.0
    path.unlink(missing_ok=True)


# ── G2: null 드라이버 AudioSystem ────────────────────────────────────────────

def test_null_driver_update():
    """G2a: NullDriver AudioSystem.update()가 예외 없이 실행된다."""
    from forge3d.audio.null_driver import NullDriver
    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)
    ew = f3d.EntityWorld()
    # 빈 ECS도 예외 없음
    sys.update(ew, 0.016)


def test_null_driver_with_sources():
    """G2b: AudioSource 컴포넌트 엔티티가 있어도 예외 없음."""
    from forge3d.audio.null_driver import NullDriver
    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)

    clip = f3d.AudioClip.from_sine()
    ew = f3d.EntityWorld()
    ew.create_entity(
        f3d.Transform(position=np.array([1.0, 0.0, 0.0])),
        f3d.AudioSource(clip=clip, auto_play=True, volume=0.8),
    )
    sys.update(ew, 0.016)
    assert driver.play_count == 1


def test_null_driver_listener():
    """G2c: AudioListener가 있어도 예외 없음."""
    from forge3d.audio.null_driver import NullDriver
    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)

    ew = f3d.EntityWorld()
    ew.create_entity(
        f3d.Transform(position=np.array([0.0, 0.0, 0.0])),
        f3d.AudioListener(gain=1.0),
    )
    sys.update(ew, 0.016)


def test_audio_system_play():
    """G2d: play()가 NullDriver.play_count를 증가시킨다."""
    from forge3d.audio.null_driver import NullDriver
    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)
    clip = f3d.AudioClip.from_sine()

    sys.play(clip, volume=0.5)
    assert driver.play_count == 1


def test_audio_system_play_at():
    """G2e: play_at()이 NullDriver.play_at_calls에 기록된다."""
    from forge3d.audio.null_driver import NullDriver
    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)
    clip = f3d.AudioClip.from_sine()
    pos = np.array([5.0, 0.0, 0.0])

    sys.play_at(clip, position=pos, volume=0.7)
    assert len(driver.play_at_calls) == 1
    assert np.allclose(driver.play_at_calls[0]["position"], pos)


# ── G3: 충돌 이벤트 연동 ─────────────────────────────────────────────────────

def test_collision_handler_trigger():
    """G3: 충돌 이벤트 콜백이 play_at()을 호출한다."""
    from forge3d.audio.null_driver import NullDriver

    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)
    clip = f3d.AudioClip.from_sine()

    handler = sys.make_collision_handler(clip, max_volume=1.0, impulse_scale=10.0)

    # 가짜 충돌 이벤트
    class FakeEvent:
        impulse = 5.0
        point = np.array([1.0, 2.0, 0.0])

    handler(FakeEvent())
    handler(FakeEvent())
    assert len(driver.play_at_calls) == 2
    assert driver.play_count == 2


def test_collision_handler_volume_scale():
    """G3b: impulse에 비례해 volume이 클램핑된다."""
    from forge3d.audio.null_driver import NullDriver

    driver = NullDriver()
    sys = f3d.AudioSystem(driver=driver)
    clip = f3d.AudioClip.from_sine()
    handler = sys.make_collision_handler(clip, max_volume=0.5, impulse_scale=10.0)

    class SmallImpact:
        impulse = 2.0
        point = np.zeros(3)

    class BigImpact:
        impulse = 100.0
        point = np.zeros(3)

    handler(SmallImpact())
    handler(BigImpact())

    vols = [c["volume"] for c in driver.play_at_calls]
    assert vols[0] < 0.5, "작은 충격은 볼륨이 작아야 함"
    assert abs(vols[1] - 0.5) < 1e-6, "큰 충격은 max_volume에 클램핑"


# ── G7: v1 API 호환 ──────────────────────────────────────────────────────────

def test_v1_api_unaffected():
    """오디오 추가 후 v1 World API가 깨지지 않는다."""
    world = f3d.World()
    body = world.add_sphere(radius=0.5, position=(0, 0, 5))
    world.step(dt=1/60)
    assert body.position[2] > 0
