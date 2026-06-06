"""AudioSystem — ECS 시스템, 오디오 드라이버 관리."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.audio.source import AudioListener, AudioSource
from forge3d.ecs.system import System
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.audio.clip import AudioClip
    from forge3d.ecs.entity import EntityWorld

logger = logging.getLogger(__name__)

_USE_AUDIO = os.environ.get("USE_AUDIO", "auto").lower()


def _create_driver() -> Any:
    """환경 변수와 사용 가능한 라이브러리에 따라 드라이버를 선택한다."""
    from forge3d.audio.null_driver import NullDriver

    if _USE_AUDIO == "0" or _USE_AUDIO == "null":
        return NullDriver()

    if _USE_AUDIO == "openal":
        from forge3d.audio.openal_driver import OpenALDriver

        return OpenALDriver()

    # auto: OpenAL 시도 후 폴백
    try:
        from forge3d.audio.openal_driver import OpenALDriver

        return OpenALDriver()
    except Exception:
        logger.debug("OpenAL 불가, NullDriver로 폴백")
        return NullDriver()


class AudioSystem(System):
    """오디오 ECS 시스템.

    - 매 프레임 AudioSource 엔티티를 순회해 auto_play 클립을 재생
    - AudioListener 위치를 드라이버에 업데이트
    - `play_at()` 으로 임의 위치에서 1회성 사운드 재생 지원
    """

    def __init__(self, driver: Any | None = None) -> None:
        self._driver = driver or _create_driver()
        self._started_entities: set[int] = set()

    @property
    def driver(self) -> Any:
        return self._driver

    # ── ECS 시스템 루프 ───────────────────────────────────────────────────────

    def update(self, ew: EntityWorld, dt: float) -> None:
        # 리스너 위치 업데이트
        for _e, tf, _al in ew.query(Transform, AudioListener):
            transform: Transform = tf  # type: ignore[assignment]
            pos = transform.position
            self._driver.set_listener(pos, np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]))
            break  # 첫 번째 리스너만 사용

        # AudioSource auto_play
        for e, tf, src in ew.query(Transform, AudioSource):
            entity = int(e)
            source: AudioSource = src  # type: ignore[assignment]
            transform = tf  # type: ignore[assignment]
            if (
                source.auto_play
                and entity not in self._started_entities
                and source.clip is not None
            ):
                self._started_entities.add(entity)
                self._driver.play_at(
                    clip=source.clip,
                    position=transform.position,
                    volume=source.volume,
                    pitch=source.pitch,
                )

    # ── 즉시 재생 API ────────────────────────────────────────────────────────

    def play(self, clip: AudioClip, volume: float = 1.0, loop: bool = False) -> None:
        """위치 없이 2D 사운드 재생 (BGM 등)."""
        self._driver.play(clip, volume=volume, loop=loop)

    def play_at(
        self,
        clip: AudioClip,
        position: np.ndarray,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> None:
        """3D 공간 위치에서 1회성 사운드 재생."""
        self._driver.play_at(
            clip, position=np.asarray(position, dtype=np.float64), volume=volume, pitch=pitch
        )

    def stop_all(self) -> None:
        self._driver.stop_all()

    def close(self) -> None:
        self._driver.close()

    # ── 충돌 이벤트 연동 헬퍼 ───────────────────────────────────────────────

    def make_collision_handler(
        self,
        clip: AudioClip,
        max_volume: float = 1.0,
        impulse_scale: float = 10.0,
    ) -> Any:
        """v1 World.on_collision_begin() 에 등록할 콜백 팩토리."""
        sys = self

        def _handler(event: Any) -> None:
            impulse = getattr(event, "impulse", impulse_scale)
            vol = min(max_volume, impulse / impulse_scale)
            pos = getattr(event, "point", np.zeros(3))
            sys.play_at(clip, position=np.asarray(pos), volume=vol)

        return _handler
