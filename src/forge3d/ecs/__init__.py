"""forge3d ECS — Entity Component System 공개 API."""
from forge3d.ecs.bridge import body_to_entity, sync_body_to_transform, sync_transform_to_body
from forge3d.ecs.component import (
    CameraComponent,
    Collider,
    Component,
    LightComponent,
    MeshRenderer,
    Rigidbody,
    Script,
)
from forge3d.ecs.entity import EntityNotFoundError, EntityWorld
from forge3d.ecs.serialization import load_scene, save_scene
from forge3d.ecs.system import PhysicsSystem, RenderSystem, ScriptSystem, System
from forge3d.ecs.transform import Transform, jax_batch_world_matrix

__all__ = [
    "Entity",
    "EntityWorld",
    "EntityNotFoundError",
    "Component",
    "Transform",
    "MeshRenderer",
    "Rigidbody",
    "Collider",
    "CameraComponent",
    "LightComponent",
    "Script",
    "System",
    "PhysicsSystem",
    "RenderSystem",
    "ScriptSystem",
    "body_to_entity",
    "sync_body_to_transform",
    "sync_transform_to_body",
    "save_scene",
    "load_scene",
    "jax_batch_world_matrix",
]

Entity = int
