"""SceneManager — 씬 로드/언로드/additive 로드 + 콜백."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld
    from forge3d.scene.node import SceneNode


class SceneManager:
    """씬 파일의 로드·언로드를 관리하는 싱글톤 스타일 매니저.

    씬 파일 = P27 `save_scene()` 포맷의 JSON.
    """

    def __init__(self, ew: "EntityWorld") -> None:
        self._ew = ew
        self._loaded_entities: list[int] = []     # 현재 씬 엔티티
        self._loaded_callbacks: list[Callable] = []
        self._unloading_callbacks: list[Callable] = []

    # ── 씬 전환 ──────────────────────────────────────────────────────────────

    def load_scene(self, path: str) -> None:
        """현재 씬을 언로드하고 새 씬을 로드한다."""
        self.unload_scene()
        self._load_from_file(path)

    def add_scene(self, path: str) -> None:
        """현재 씬에 중첩(additive)으로 씬을 추가한다."""
        self._load_from_file(path)

    def unload_scene(self) -> None:
        """현재 씬의 모든 엔티티를 소멸시킨다."""
        for callback in self._unloading_callbacks:
            try:
                callback()
            except Exception:
                pass

        for e in self._loaded_entities:
            try:
                if self._ew.is_alive(e):
                    self._ew.destroy_entity(e)
            except Exception:
                pass
        self._loaded_entities.clear()

    # ── 콜백 등록 ────────────────────────────────────────────────────────────

    def on_scene_loaded(self, callback: Callable) -> None:
        """씬 로드 완료 후 호출될 콜백을 등록한다."""
        self._loaded_callbacks.append(callback)

    def on_scene_unloading(self, callback: Callable) -> None:
        """씬 언로드 시작 전 호출될 콜백을 등록한다."""
        self._unloading_callbacks.append(callback)

    # ── 씬 파일 I/O ──────────────────────────────────────────────────────────

    def _load_from_file(self, path: str) -> None:
        from forge3d.ecs.serialization import load_scene

        before = set(self._ew.all_entities())
        temp_ew = load_scene(path)

        # temp_ew의 컴포넌트를 현재 ew로 이식
        for e in temp_ew.all_entities():
            comps = list(temp_ew.components_of(e).values())
            new_entity = self._ew.create_entity(*comps)
            self._loaded_entities.append(new_entity)

        for callback in self._loaded_callbacks:
            try:
                callback()
            except Exception:
                pass

    @property
    def entity_count(self) -> int:
        """현재 씬의 살아있는 엔티티 수."""
        return sum(1 for e in self._loaded_entities if self._ew.is_alive(e))
