"""forge3d.io — 3D asset loading utilities.

from forge3d.io import load_obj
mesh = load_obj("path/to/model.obj")
"""

from forge3d.io.mesh_data import MeshData
from forge3d.io.obj_loader import load_obj

__all__ = ["MeshData", "load_obj"]
