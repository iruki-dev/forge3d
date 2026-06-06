"""RenderPass ABC — 파이프라인 패스 단위 추상."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import moderngl


class RenderPass(ABC):
    """지연 렌더링 파이프라인의 단위 패스."""

    @abstractmethod
    def setup(self, ctx: moderngl.Context, size: tuple[int, int]) -> None:
        """FBO, 텍스처, 셰이더 등 GPU 리소스 초기화."""

    @abstractmethod
    def render(self, ctx: moderngl.Context, data: Any) -> None:
        """패스 실행. data는 패스별로 다름 (SceneSnapshot 또는 이전 패스 출력)."""

    def resize(self, size: tuple[int, int]) -> None:  # noqa: B027
        """뷰포트 크기 변경 시 호출 (선택 구현)."""
