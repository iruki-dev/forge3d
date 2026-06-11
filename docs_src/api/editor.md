# forge3d.editor — In-Engine Editor

forge3d ships an in-engine scene editor with play/pause/step controls,
entity selection, transform gizmos, and a hierarchy/inspector panel.

---

## EditorApp

::: forge3d.editor.EditorApp
    options:
      members:
        - __init__
        - play
        - pause
        - stop
        - step_once
        - play_state
        - is_playing
        - is_paused
        - is_editing
        - update
        - pick_entity
        - move_selected
        - save_scene
        - on_scene_saved
        - set_scene_path
        - run_headless
        - run

---

## Gizmos

::: forge3d.editor.TranslateGizmo

::: forge3d.editor.GizmoMode

::: forge3d.editor.screen_to_ray

---

## Usage examples

### Launch the editor

```python
import forge3d as f3d

world = f3d.World()
ew = f3d.EntityWorld()

editor = f3d.EditorApp(world, ew, title="My Scene")

# Populate the scene
ew.create_entity(
    f3d.Transform(position=[0, 0, 2]),
    f3d.MeshRenderer(shape="box", size=(1, 1, 1)),
)

editor.run()   # opens an OS window with the editor UI
```

### Headless testing (CI-safe)

```python
editor = f3d.EditorApp(world, ew)
editor.run_headless(n_frames=10)   # run 10 update cycles without a window
```

### Play/pause/step controls

```python
editor.play()            # start simulation
editor.pause()           # freeze time
editor.step_once()       # advance exactly one physics tick while paused
editor.stop()            # revert to pre-play snapshot

print(editor.play_state)   # PlayState.PLAYING | PAUSED | EDITING
```

### Transform gizmo

```python
from forge3d.editor import TranslateGizmo
import numpy as np

gizmo = TranslateGizmo()

# Ray from camera
origin    = np.array([0., 0., 10.])
direction = np.array([0., 0., -1.])

hit_entity = editor.pick_entity(
    ew,
    view_matrix=np.eye(4),
    ray_origin=origin,
    ray_dir=direction,
)
if hit_entity is not None:
    editor.move_selected(axis=0, delta=0.1)   # move +X by 0.1 m
```

### Save scene

```python
editor.set_scene_path("scenes/level1.json")
editor.save_scene()                  # save to configured path
editor.save_scene("scenes/bak.json") # override path
```
