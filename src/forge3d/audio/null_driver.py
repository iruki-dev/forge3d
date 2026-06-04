"""Null 오디오 드라이버 — 헤드리스 환경 no-op 구현.

오디오 하드웨어가 없는 서버·CI 환경에서 AudioSystem이 예외를 던지지 않도록 한다.
실제 소리는 출력되지 않는다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.audio.clip import AudioClip


class NullDriver:
    """오디오 하드웨어 없이 동작하는 no-op 드라이버."""

    # 재생 요청 횟수 (테스트 검증용)
    play_count: int = 0
    play_at_calls: list[dict] = []

    def __init__(self) -> None:
        self.play_count = 0
        self.play_at_calls = []

    def play(self, clip: "AudioClip", volume: float = 1.0, loop: bool = False) -> None:
        self.play_count += 1

    def play_at(
        self,
        clip: "AudioClip",
        position: np.ndarray,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> None:
        self.play_count += 1
        self.play_at_calls.append({"clip": clip, "position": position, "volume": volume})

    def stop_all(self) -> None:
        pass

    def set_listener(self, position: np.ndarray, forward: np.ndarray, up: np.ndarray) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def is_available(self) -> bool:
        return True
