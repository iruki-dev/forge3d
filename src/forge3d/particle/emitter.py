"""ParticleEmitter — ECS 컴포넌트 + VFX 프리셋."""

from __future__ import annotations

from dataclasses import dataclass

from forge3d.ecs.component import Component


@dataclass
class ParticleEmitter(Component):
    """파티클 생성 설정 ECS 컴포넌트.

    ParticleSystem이 매 프레임 이 컴포넌트를 읽어 파티클을 생성한다.
    """

    rate: float = 100.0  # 파티클/초
    lifetime: float = 2.0  # 각 파티클 수명 (초)
    initial_speed: float = 5.0  # 초기 속도 (m/s)
    spread_angle: float = 30.0  # 분사 원뿔 반각 (도)
    gravity: float = -9.81  # 중력 가속도 (m/s²)
    restitution: float = 0.3  # 지면 반발계수
    ground_y: float = 0.0  # 지면 y 좌표
    max_particles: int = 10_000  # 최대 파티클 수 (풀 크기)
    color_start: tuple[float, float, float, float] = (1.0, 0.8, 0.2, 1.0)  # RGBA
    color_end: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # RGBA (수명 끝)
    active: bool = True

    @classmethod
    def preset(cls, name: str, **kwargs: object) -> ParticleEmitter:
        """VFX 프리셋 팩토리."""
        presets = {
            "sparks": {
                "rate": 500,
                "lifetime": 0.5,
                "initial_speed": 8.0,
                "spread_angle": 60.0,
                "gravity": -9.81,
                "restitution": 0.5,
                "color_start": (1.0, 0.9, 0.3, 1.0),
                "color_end": (0.8, 0.2, 0.0, 0.0),
            },
            "smoke": {
                "rate": 50,
                "lifetime": 3.0,
                "initial_speed": 1.0,
                "spread_angle": 20.0,
                "gravity": -0.2,
                "restitution": 0.0,
                "color_start": (0.6, 0.6, 0.6, 0.8),
                "color_end": (0.3, 0.3, 0.3, 0.0),
            },
            "debris": {
                "rate": 80,
                "lifetime": 1.5,
                "initial_speed": 4.0,
                "spread_angle": 90.0,
                "gravity": -9.81,
                "restitution": 0.4,
                "color_start": (0.5, 0.4, 0.3, 1.0),
                "color_end": (0.2, 0.15, 0.1, 0.0),
            },
            "rain": {
                "rate": 300,
                "lifetime": 1.0,
                "initial_speed": 6.0,
                "spread_angle": 5.0,
                "gravity": -9.81,
                "restitution": 0.0,
                "color_start": (0.5, 0.7, 1.0, 0.7),
                "color_end": (0.5, 0.7, 1.0, 0.0),
            },
        }
        base = presets.get(name, {})
        base.update(kwargs)
        return cls(**base)
