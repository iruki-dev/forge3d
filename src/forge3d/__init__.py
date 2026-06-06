"""forge3d — pure-Python 3D game engine.

"Fast like native, beautiful like simulation."
Coordinate system: z-up, SI units (metres, kg, seconds).

Minimal example (14 lines)::

    import forge3d as f3d

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    viewer = f3d.Viewer(world, max_frames=90)
    while viewer.is_open:
        world.step(dt=1 / 60)
        viewer.draw()
    print(f"Box final z = {box.position[2]:.2f} m")

App-style game loop::

    app = f3d.App("My World")

    @app.on_start
    def setup(world):
        world.add_ground()
        global ball
        ball = world.add_sphere(position=(0, 0, 5))

    @app.on_update
    def update(world, dt, inp):
        if inp.key_pressed(f3d.Key.SPACE):
            world.apply_impulse(ball, (0, 0, 8))

    app.run()

Load a 3D model::

    from forge3d.io import load_obj
    mesh = load_obj("assets/models/cube.obj")
    body = world.add_mesh(mesh, position=(0, 0, 3), mass=1.0)

Public API:
    App       — game-loop abstraction (on_start, on_update, on_render)
    World     — physics world with scene construction helpers
    Body      — handle to a simulated rigid body
    Shape     — shape descriptor (box, sphere, capsule, mesh)
    Material  — surface appearance (PBR: color, roughness, metallic, texture)
    Viewer    — realtime render loop + Input access
    Recorder  — capture simulation to video / image sequence
    Input     — per-frame keyboard/mouse state snapshot
    Key       — keyboard key name constants
    OrbitCamera   — orbit-around-target camera controller
    FollowCamera  — smooth body-tracking camera controller
"""

from __future__ import annotations

# Animation (P29)
from forge3d.animation import (
    AnimationClip,
    AnimationPlayer,
    AnimationSystem,
    BlendTree,
    Bone,
    FABRIKSolver,
    IKTarget,
    Skeleton,
)
from forge3d.app import App

# Audio (P28)
from forge3d.audio import AudioClip, AudioListener, AudioSource, AudioSystem
from forge3d.backend import backend_name as _backend_name  # noqa: F401
from forge3d.camera import FollowCamera, OrbitCamera
from forge3d.character import CharacterController
from forge3d.collision.layers import CollisionLayer
from forge3d.constraints import JointHandle
from forge3d.constraints.joint_type import JointType

# ECS (P27)
from forge3d.ecs import (
    CameraComponent,
    Collider,
    Component,
    EntityNotFoundError,
    EntityWorld,
    LightComponent,
    MeshRenderer,
    PhysicsSystem,
    RenderSystem,
    Rigidbody,
    Script,
    ScriptSystem,
    System,
    Transform,
    body_to_entity,
    load_scene,
    save_scene,
)

# Editor (P33)
from forge3d.editor import EditorApp, PlayState
from forge3d.errors import Forge3dError, PhysicsError, RenderError, ValidationError
from forge3d.events import CollisionEvent, CollisionHandler
from forge3d.facade import Body, Material, Shape, World
from forge3d.input import Input, InputBuilder, Key
from forge3d.io.world_snapshot import StateRecorder

# Particle system (P31)
from forge3d.particle import ParticleEmitter, ParticleSystem
from forge3d.particle.presets import smoke as particle_smoke
from forge3d.particle.presets import sparks as particle_sparks
from forge3d.profiler import PhysicsProfile, PhysicsProfiler
from forge3d.recorder import Recorder
from forge3d.render.snapshot import TerrainSnapshot

# Scene management (P30)
from forge3d.scene import Prefab, SceneManager, SceneNode

# UI system (P32)
from forge3d.ui import Canvas, DebugPanel, HierarchyPanel, InspectorPanel, UISystem
from forge3d.viewer import Viewer

__version__ = "2.1.0"

# ── API 안정성 선언 ───────────────────────────────────────────────────────────
# Stable (v3까지 Breaking change 없음):
#   World, Body, Shape, Material, App, Viewer, Recorder, Input, OrbitCamera
#   EntityWorld, Transform, Rigidbody, Collider, MeshRenderer, Script
#   PhysicsSystem, RenderSystem, AudioSystem, AnimationPlayer, FABRIKSolver
#   SceneManager, Prefab, ParticleEmitter, DebugPanel, Canvas
# Experimental (v2.x에서 변경 가능):
#   forge3d._core, forge3d.render.wgpu_backend, forge3d.editor
__all__ = [
    # Core
    "World",
    "Body",
    "Shape",
    "Material",
    # Joints
    "JointHandle",
    "JointType",
    # Character
    "CharacterController",
    # Profiler
    "PhysicsProfiler",
    "PhysicsProfile",
    # Events
    "CollisionEvent",
    "CollisionHandler",
    # Collision layers
    "CollisionLayer",
    # Serialization
    "StateRecorder",
    # Game loop
    "App",
    # Input
    "Input",
    "InputBuilder",
    "Key",
    # Camera
    "OrbitCamera",
    "FollowCamera",
    # Output
    "Viewer",
    "Recorder",
    # Errors
    "Forge3dError",
    "ValidationError",
    "PhysicsError",
    "RenderError",
    # Snapshot
    "TerrainSnapshot",
    # Version
    "__version__",
    # Editor (P33)
    "EditorApp",
    "PlayState",
    # UI system (P32)
    "DebugPanel",
    "InspectorPanel",
    "HierarchyPanel",
    "Canvas",
    "UISystem",
    # Particle system (P31)
    "ParticleEmitter",
    "ParticleSystem",
    "particle_sparks",
    "particle_smoke",
    # Scene management (P30)
    "SceneNode",
    "Prefab",
    "SceneManager",
    # Animation (P29)
    "Bone",
    "Skeleton",
    "AnimationClip",
    "AnimationPlayer",
    "BlendTree",
    "IKTarget",
    "FABRIKSolver",
    "AnimationSystem",
    # Audio (P28)
    "AudioClip",
    "AudioSource",
    "AudioListener",
    "AudioSystem",
    # ECS (P27)
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
    "save_scene",
    "load_scene",
]
