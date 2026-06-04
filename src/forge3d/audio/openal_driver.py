"""OpenAL 3D 오디오 드라이버.

openal-python 패키지가 설치돼 있고 오디오 디바이스가 있을 때만 활성화된다.
그렇지 않으면 NullDriver로 폴백한다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.audio.clip import AudioClip

logger = logging.getLogger(__name__)


def _try_create() -> Any:
    """OpenAL 컨텍스트 생성을 시도한다. 실패하면 None 반환."""
    try:
        from openal import al, alc  # type: ignore[import]
        device = alc.alcOpenDevice(None)
        if not device:
            return None
        ctx = alc.alcCreateContext(device, None)
        if not ctx:
            alc.alcCloseDevice(device)
            return None
        alc.alcMakeContextCurrent(ctx)
        return (device, ctx, al, alc)
    except Exception:
        return None


class OpenALDriver:
    """PyOpenAL 기반 3D 공간음 드라이버."""

    MAX_SOURCES = 32

    def __init__(self) -> None:
        result = _try_create()
        if result is None:
            raise RuntimeError("OpenAL 디바이스를 초기화할 수 없습니다")
        self._device, self._ctx, self._al, self._alc = result
        al = self._al
        self._source_pool: list[int] = list(al.alGenSources(self.MAX_SOURCES))
        self._buf_cache: dict[str, int] = {}
        self.play_count = 0
        self.play_at_calls: list[dict] = []

    def _get_buffer(self, clip: "AudioClip") -> int:
        if clip.name in self._buf_cache:
            return self._buf_cache[clip.name]
        al = self._al
        buf = al.alGenBuffers(1)[0]
        pcm = clip.to_pcm16()
        fmt = al.AL_FORMAT_MONO16 if clip.channels == 1 else al.AL_FORMAT_STEREO16
        al.alBufferData(buf, fmt, pcm, len(pcm), clip.sample_rate)
        self._buf_cache[clip.name] = buf
        return buf

    def _next_source(self) -> int | None:
        al = self._al
        for src in self._source_pool:
            state = al.alGetSourcei(src, al.AL_SOURCE_STATE)
            if state != al.AL_PLAYING:
                return src
        return None

    def play(self, clip: "AudioClip", volume: float = 1.0, loop: bool = False) -> None:
        src = self._next_source()
        if src is None:
            return
        al = self._al
        buf = self._get_buffer(clip)
        al.alSourcei(src, al.AL_BUFFER, buf)
        al.alSourcef(src, al.AL_GAIN, volume)
        al.alSourcei(src, al.AL_LOOPING, al.AL_TRUE if loop else al.AL_FALSE)
        al.alSource3f(src, al.AL_POSITION, 0.0, 0.0, 0.0)
        al.alSourcePlay(src)
        self.play_count += 1

    def play_at(
        self,
        clip: "AudioClip",
        position: np.ndarray,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> None:
        src = self._next_source()
        if src is None:
            return
        al = self._al
        buf = self._get_buffer(clip)
        al.alSourcei(src, al.AL_BUFFER, buf)
        al.alSourcef(src, al.AL_GAIN, volume)
        al.alSourcef(src, al.AL_PITCH, pitch)
        al.alSource3f(src, al.AL_POSITION, *position[:3].astype(float))
        al.alSourcePlay(src)
        self.play_count += 1
        self.play_at_calls.append({"clip": clip, "position": position, "volume": volume})

    def set_listener(self, position: np.ndarray, forward: np.ndarray, up: np.ndarray) -> None:
        al = self._al
        al.alListener3f(al.AL_POSITION, *position[:3].astype(float))
        orientation = np.concatenate([forward[:3], up[:3]]).astype(np.float32)
        al.alListenerfv(al.AL_ORIENTATION, orientation)

    def stop_all(self) -> None:
        al = self._al
        for src in self._source_pool:
            al.alSourceStop(src)

    def close(self) -> None:
        al, alc = self._al, self._alc
        for buf in self._buf_cache.values():
            al.alDeleteBuffers(1, [buf])
        al.alDeleteSources(self._source_pool)
        alc.alcMakeContextCurrent(None)
        alc.alcDestroyContext(self._ctx)
        alc.alcCloseDevice(self._device)

    @property
    def is_available(self) -> bool:
        return True
