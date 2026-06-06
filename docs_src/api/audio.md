# forge3d.audio — 3D Spatial Audio

forge3d's audio system provides 3D positional sound with automatic fallback to a
no-op driver in headless / CI environments.

!!! note "Dependency"
    Real audio output requires OpenAL (`pip install openal-soft` or system package).
    In environments without audio hardware, `AudioSystem` automatically uses
    `NullDriver` — all API calls succeed silently.

---

## Classes

::: forge3d.audio.AudioClip

::: forge3d.audio.AudioSource

::: forge3d.audio.AudioListener

::: forge3d.audio.AudioSystem

---

## Usage examples

### Load and play a sound

```python
from forge3d import AudioSystem, AudioClip, AudioSource, AudioListener

audio = AudioSystem()

# Load audio file (WAV or OGG)
clip = AudioClip.load("assets/sounds/thud.wav")

# Create a 3D source at a world position
source = AudioSource(position=(3, 0, 1), volume=0.8, loop=False)
audio.play(source, clip)
```

### Attach to physics body

```python
import forge3d as f3d

world = f3d.World()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

audio = f3d.AudioSystem()
impact_clip = f3d.AudioClip.load("impact.wav")

@world.on_collision_begin
def on_hit(event: f3d.CollisionEvent) -> None:
    if event.relative_speed > 2.0:
        source = f3d.AudioSource(
            position=tuple(event.body_a.position),
            volume=min(1.0, event.relative_speed / 10.0),
        )
        audio.play(source, impact_clip)
```

### 3D listener (camera-relative)

```python
# Move the listener to follow the camera each frame
listener = f3d.AudioListener()
cam_pos = np.array([4.0, -7.0, 3.0])
listener.position = cam_pos
listener.forward = np.array([0.0, 1.0, 0.0])   # direction camera looks
audio.set_listener(listener)
```

### Background music

```python
music = AudioClip.load("assets/music/ambient.ogg")
bgm_source = AudioSource(
    position=(0, 0, 0),   # world-space but audible everywhere
    volume=0.4,
    loop=True,
)
audio.play(bgm_source, music)
```

### AudioSystem integration with App

```python
import forge3d as f3d

app = f3d.App("Sound Demo")
audio = f3d.AudioSystem()

@app.on_start
def setup(world: f3d.World) -> None:
    bgm = f3d.AudioClip.load("music.ogg")
    audio.play(f3d.AudioSource(loop=True, volume=0.5), bgm)

@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    audio.update(dt)   # advance source positions

app.run()
```
