"""EntityWorld — ECS 엔티티 생성/소멸/컴포넌트 관리."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, TypeVar

from forge3d.ecs.component import Component
from forge3d.errors import Forge3dError

Entity = int
C = TypeVar("C", bound=Component)

_ENTITY_COUNTER = itertools.count(1)


class EntityNotFoundError(Forge3dError):
    """소멸된 엔티티에 접근할 때 발생."""


class EntityWorld:
    """ECS 월드 — 엔티티 생명주기와 컴포넌트 저장소."""

    def __init__(self) -> None:
        # {ComponentType: {entity_id: component_instance}}
        self._components: dict[type[Component], dict[Entity, Component]] = {}
        self._alive: set[Entity] = set()
        self._systems: list[object] = []  # System 인스턴스

    # ── 엔티티 생명주기 ──────────────────────────────────────────────────────

    def create_entity(self, *components: Component) -> Entity:
        """컴포넌트 목록으로 새 엔티티를 생성한다."""
        e = next(_ENTITY_COUNTER)
        self._alive.add(e)
        for comp in components:
            self.add_component(e, comp)
        return e

    def destroy_entity(self, e: Entity) -> None:
        """엔티티와 그 컴포넌트를 모두 삭제한다."""
        if e not in self._alive:
            raise EntityNotFoundError(f"엔티티 {e}는 이미 소멸됐거나 존재하지 않습니다")
        self._alive.discard(e)
        for store in self._components.values():
            store.pop(e, None)

    def is_alive(self, e: Entity) -> bool:
        return e in self._alive

    # ── 컴포넌트 CRUD ─────────────────────────────────────────────────────────

    def add_component(self, e: Entity, c: Component) -> None:
        if e not in self._alive:
            raise EntityNotFoundError(f"엔티티 {e}가 존재하지 않습니다")
        typ = type(c)
        if typ not in self._components:
            self._components[typ] = {}
        self._components[typ][e] = c

    def remove_component(self, e: Entity, typ: type[C]) -> None:
        if e not in self._alive:
            raise EntityNotFoundError(f"엔티티 {e}가 존재하지 않습니다")
        store = self._components.get(typ, {})
        store.pop(e, None)

    def get_component(self, e: Entity, typ: type[C]) -> C:
        if e not in self._alive:
            raise EntityNotFoundError(f"엔티티 {e}가 존재하지 않습니다")
        store = self._components.get(typ, {})
        if e not in store:
            raise KeyError(f"엔티티 {e}에 {typ.__name__} 컴포넌트 없음")
        return store[e]  # type: ignore[return-value]

    def has_component(self, e: Entity, typ: type[Component]) -> bool:
        return e in self._components.get(typ, {})

    # ── 쿼리 ─────────────────────────────────────────────────────────────────

    def query(self, *types: type[Component]) -> Iterator[tuple[Entity, ...]]:
        """모든 지정 타입을 가진 엔티티와 컴포넌트 튜플을 순회한다.

        반환: (entity, comp_type1_inst, comp_type2_inst, ...)
        """
        if not types:
            return
        # 가장 작은 저장소를 기준으로 교집합
        stores = [self._components.get(t, {}) for t in types]
        smallest = min(stores, key=len)
        for e in list(smallest.keys()):
            if e not in self._alive:
                continue
            row: list[Any] = [e]
            ok = True
            for t in types:
                store = self._components.get(t, {})
                if e not in store:
                    ok = False
                    break
                row.append(store[e])
            if ok:
                yield tuple(row)  # type: ignore[misc]

    # ── 시스템 ───────────────────────────────────────────────────────────────

    def add_system(self, system: object) -> None:
        self._systems.append(system)

    def step(self, dt: float) -> None:
        """등록된 모든 System.update()를 순서대로 실행한다."""
        for sys in self._systems:
            if hasattr(sys, "update"):
                sys.update(self, dt)

    # ── 직렬화 지원 ──────────────────────────────────────────────────────────

    def all_entities(self) -> list[Entity]:
        return list(self._alive)

    def components_of(self, e: Entity) -> dict[type[Component], Component]:
        result: dict[type[Component], Component] = {}
        for typ, store in self._components.items():
            if e in store:
                result[typ] = store[e]
        return result
