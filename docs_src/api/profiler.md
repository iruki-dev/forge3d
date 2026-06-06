# forge3d.PhysicsProfiler

The physics profiler measures how long each phase of `world.step()` takes so
you can identify bottlenecks.

---

## Classes

::: forge3d.profiler.PhysicsProfiler
    options:
      members:
        - step
        - last
        - average
        - history
        - reset
        - __enter__
        - __exit__

::: forge3d.profiler.PhysicsProfile

---

## Usage

### Measure one step manually

```python
import forge3d as f3d

world = f3d.World()
world.add_ground()
world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

world.profiler.step(dt=1/60)    # measures this single step

p = world.profiler.last
print(f"Total: {p.total*1000:.3f} ms")
print(f"  broadphase:  {p.broadphase*1000:.3f} ms")
print(f"  narrowphase: {p.narrowphase*1000:.3f} ms")
print(f"  solver:      {p.solver*1000:.3f} ms")
print(f"  integration: {p.integration*1000:.3f} ms")
print(f"  contacts:    {p.contacts}")
```

### Context manager (wraps world.step)

```python
with world.profiler:
    world.step(dt=1/60)

print(world.profiler.last)
```

### Rolling average (smooth HUD display)

```python
viewer = f3d.Viewer(world, title="Profile Demo")
while viewer.is_open:
    world.step(dt=viewer.dt)

    avg = world.profiler.average(n=60)   # last-60-frame average
    ms = avg.total * 1000
    viewer.draw_text(f"Physics: {ms:.2f} ms ({avg.contacts} contacts)",
                     x=10, y=10, size=18)
    viewer.draw()
```

---

## PhysicsProfile fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | `float` | Total `world.step()` wall time (seconds) |
| `broadphase` | `float` | AABB overlap check time |
| `narrowphase` | `float` | GJK/EPA / SAT time |
| `solver` | `float` | PGS contact solve time |
| `integration` | `float` | Semi-implicit Euler integration time |
| `joints` | `float` | Joint constraint solve time |
| `contacts` | `int` | Number of active contact points this step |
| `bodies` | `int` | Number of dynamic (non-sleeping) bodies |
| `sleeping` | `int` | Number of sleeping bodies skipped |
