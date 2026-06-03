# Backend switching (NumPy / JAX)

forge3d supports two computation backends that can be switched at runtime:

```bash
ENGINE_BACKEND=numpy python my_script.py   # default
ENGINE_BACKEND=jax   python my_script.py   # JAX JIT + vmap
```

Both backends produce numerically equivalent results (within float64 tolerance).

---

## Why two backends?

- **NumPy**: Simple, debuggable, no JIT overhead for small scenes.
- **JAX**: JIT compilation + `vmap` batching → 2,000× throughput for RL training.

The JAX backend shines when stepping thousands of environments in parallel:

```python
import jax
import jax.numpy as jnp
from forge3d.sim.jax_batch import batch_reach_reset, batch_reach_step

key = jax.random.PRNGKey(0)
q, tgt, obs = batch_reach_reset(key, n_envs=256)
q, obs, rew, done = batch_reach_step(q, tgt, jnp.zeros((256, 6)))
```

---

## Backend API

::: forge3d.backend
