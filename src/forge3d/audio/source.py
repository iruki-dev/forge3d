"""AudioSource + AudioListener ECS 컴포넌트."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from forge3d.ecs.component import Component

if TYPE_CHECKING:
    from forge3d.audio.clip import AudioClip


@dataclass
class AudioSource(Component):
    """3D 공간에서 소리를 발생시키는 ECS 컴포넌트."""

    clip: AudioClip | None = None
    volume: float = 1.0
    pitch: float = 1.0
    loop: bool = False
    min_distance: float = 1.0  # 감쇠 시작 거리 (m)
    max_distance: float = 50.0  # 감쇠 최대 거리 (m)
    auto_play: bool = False
    _playing: bool = field(default=False, repr=False)
    _source_handle: Any = field(default=None, repr=False)  # OpenAL 소스 핸들


@dataclass
class AudioListener(Component):
    """월드에서 소리를 듣는 청취 위치 ECS 컴포넌트.

    보통 카메라 엔티티에 부착한다.
    """

    gain: float = 1.0  # 마스터 볼륨
