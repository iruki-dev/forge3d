"""forge3d — pure-Python 3D game engine.

"Easy like pygame, beautiful like simulation."
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

from forge3d.app import App
from forge3d.render.snapshot import TerrainSnapshot
from forge3d.errors import Forge3dError, PhysicsError, RenderError, ValidationError
from forge3d.backend import backend_name as _backend_name  # noqa: F401
from forge3d.camera import FollowCamera, OrbitCamera
from forge3d.constraints import JointHandle
from forge3d.collision.layers import CollisionLayer
from forge3d.events import CollisionEvent, CollisionHandler
from forge3d.facade import Body, Material, Shape, World
from forge3d.input import Input, InputBuilder, Key
from forge3d.io.world_snapshot import StateRecorder
from forge3d.recorder import Recorder
from forge3d.viewer import Viewer

__version__ = "1.1.0"
__all__ = [
    # Core
    "World",
    "Body",
    "Shape",
    "Material",
    # Joints
    "JointHandle",
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
]
