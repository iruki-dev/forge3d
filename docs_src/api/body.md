# forge3d.Body

A handle to a single rigid body in the simulation. Returned by every `World.add_*` call.

::: forge3d.facade.Body
    options:
      members:
        - position
        - velocity
        - orientation
        - angular_velocity
        - name
        - is_static
        - mass
        - apply_force
        - apply_torque
        - set_position
        - set_orientation
        - set_velocity
        - set_angular_velocity

---

## Examples

```python
world = f3d.World()
box = world.add_box(size=(1,1,1), position=(0,0,5), mass=2.0)

print(box.position)           # [0. 0. 5.]
print(box.mass)               # 2.0

box.apply_force((10, 0, 0))   # 10 N in +x for the next step
world.step(dt=1/60)
print(box.velocity)           # v_x ≈ 0.083 m/s
```
