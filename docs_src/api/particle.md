# forge3d.particle — Particle System

forge3d's particle system supports CPU-based emitters with configurable spawn
rates, velocities, lifetimes, and rendering via the realtime renderer.

---

## Classes

::: forge3d.particle.ParticleEmitter

::: forge3d.particle.ParticleSystem

---

## Built-in presets

```python
from forge3d import particle_sparks, particle_smoke
from forge3d.particle.presets import rain, debris
```

| Preset | Description |
|--------|-------------|
| `particle_sparks` | Short-lived bright sparks with downward gravity |
| `particle_smoke` | Slow-rising dark particles with fade-out |
| `rain` | Downward streaks with high emission rate |
| `debris` | Random tumbling fragments from an explosion |

---

## Usage examples

### Basic emitter

```python
import forge3d as f3d
import numpy as np

world = f3d.World()

emitter = f3d.ParticleEmitter(
    position=np.array([0.0, 0.0, 1.0]),
    rate=50.0,            # particles per second
    lifetime=(0.5, 2.0),  # (min, max) seconds
    speed=(0.5, 3.0),     # (min, max) initial speed m/s
    spread_angle=30.0,    # cone half-angle in degrees
    gravity_scale=1.0,    # gravity multiplier
    color=(1.0, 0.6, 0.1),
    size=(0.02, 0.08),    # (min, max) radius
)

ps = f3d.ParticleSystem()
ps.add(emitter)

dt = 1 / 60
for _ in range(300):
    ps.update(dt)
    world.step(dt)
```

### Preset sparks at a collision point

```python
@world.on_collision_begin
def on_hit(event: f3d.CollisionEvent) -> None:
    if event.relative_speed > 3.0:
        sparks = f3d.particle_sparks()
        sparks.position = event.body_a.position.copy()
        ps.add(sparks)
        # One-shot: auto-remove after particles die
        ps.add(sparks, one_shot=True)
```

### Attach emitter to a moving body

```python
rocket = world.add_sphere(radius=0.2, position=(0, 0, 2), mass=0.5)
thruster = f3d.particle_smoke()

@app.on_update
def update(world, dt, inp):
    thruster.position = rocket.position.copy()
    thruster.direction = -np.array(rocket.velocity + [1e-6, 0, 0])
    ps.update(dt)
```

### ParticleSystem cleanup

```python
ps.clear()          # remove all active emitters
ps.remove(emitter)  # remove a specific emitter
```
