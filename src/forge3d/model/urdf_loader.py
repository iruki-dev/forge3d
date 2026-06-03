"""Minimal URDF parser — loads a serial-chain URDF into RigidBodyModel.

Supports:
- Revolute and prismatic joints
- <inertial> with <origin xyz/rpy>, <mass>, <inertia ixx ... izz>
- <joint> with <parent>, <child>, <origin xyz/rpy>, <axis xyz>

Limitations (sufficient for P2 validation):
- Single kinematic chain only (no branching for multi-arm)
- Fixed joints are folded into the parent's transform
- No mesh geometry (physics only)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.se3 import rot_x, rot_y, rot_z
from forge3d.model.robot_config import JointConfig, LinkConfig, build_model

# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_xyz(text: str | None) -> np.ndarray:
    if text is None:
        return np.zeros(3)
    return np.array([float(v) for v in text.strip().split()])


def _parse_rpy(text: str | None) -> np.ndarray:
    if text is None:
        return np.zeros(3)
    return np.array([float(v) for v in text.strip().split()])


def _rpy_to_R(rpy: np.ndarray) -> np.ndarray:
    """Roll-pitch-yaw (ZYX intrinsic) → 3x3 rotation matrix.

    R = Rz(yaw) * Ry(pitch) * Rx(roll)
    """
    roll, pitch, yaw = rpy
    return rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)


# ── URDF loader ───────────────────────────────────────────────────────────────


def load_urdf(
    urdf_path: str,
    gravity: Any = None,
) -> RigidBodyModel:
    """Parse a URDF file and return a RigidBodyModel.

    Parameters
    ----------
    urdf_path : path to the URDF file.
    gravity   : (3,) world-frame gravity vector (default: [0, 0, -9.81]).
    """
    tree = ET.parse(urdf_path)
    root = tree.getroot()

    # ── collect links and joints ────────────────────────────────────────────
    link_map: dict[str, dict] = {}
    for link_el in root.findall("link"):
        name = link_el.get("name", "")
        inertial = link_el.find("inertial")
        if inertial is None:
            link_map[name] = {"mass": 0.0, "com": np.zeros(3), "inertia": np.zeros((3, 3))}
            continue

        origin = inertial.find("origin")
        xyz = _parse_xyz(origin.get("xyz") if origin is not None else None)
        rpy = _parse_rpy(origin.get("rpy") if origin is not None else None)
        R_com = _rpy_to_R(rpy)
        # The inertia tensor is given in the CoM-aligned frame; after rotation by
        # R_com, it is transformed into the joint frame.
        # For diagonal tensors in a CoM frame with no rotation, R_com = I3.

        mass_el = inertial.find("mass")
        mass = float(mass_el.get("value", "0")) if mass_el is not None else 0.0

        inertia_el = inertial.find("inertia")
        if inertia_el is not None:
            ixx = float(inertia_el.get("ixx", "0"))
            ixy = float(inertia_el.get("ixy", "0"))
            ixz = float(inertia_el.get("ixz", "0"))
            iyy = float(inertia_el.get("iyy", "0"))
            iyz = float(inertia_el.get("iyz", "0"))
            izz = float(inertia_el.get("izz", "0"))
            Icm_com_frame = np.array(
                [
                    [ixx, ixy, ixz],
                    [ixy, iyy, iyz],
                    [ixz, iyz, izz],
                ]
            )
            # Rotate inertia into joint frame: I_joint = R_com * I_com * R_com^T
            Icm = R_com @ Icm_com_frame @ R_com.T
        else:
            Icm = np.zeros((3, 3))

        # CoM position in joint frame (accounting for rotation of CoM frame)
        com = xyz  # CoM origin in joint frame

        link_map[name] = {"mass": mass, "com": com, "inertia": Icm}

    joint_list: list[dict] = []
    for joint_el in root.findall("joint"):
        jtype = joint_el.get("type", "fixed")
        parent_name = joint_el.find("parent").get("link", "")  # type: ignore[union-attr]
        child_name = joint_el.find("child").get("link", "")  # type: ignore[union-attr]

        origin = joint_el.find("origin")
        xyz = _parse_xyz(origin.get("xyz") if origin is not None else None)
        rpy = _parse_rpy(origin.get("rpy") if origin is not None else None)
        R_joint = _rpy_to_R(rpy)

        axis_el = joint_el.find("axis")
        axis = _parse_xyz(axis_el.get("xyz") if axis_el is not None else None)
        if np.linalg.norm(axis) < 1e-10:
            axis = np.array([0.0, 0.0, 1.0])

        joint_list.append(
            {
                "type": jtype,
                "parent": parent_name,
                "child": child_name,
                "origin_xyz": xyz,
                "origin_R": R_joint,
                "axis": axis,
            }
        )

    # ── build ordered link/joint lists (topological sort for serial chain) ──
    # Find the root link (not mentioned as a child of any joint)
    all_children = {j["child"] for j in joint_list}
    root_links = [name for name in link_map if name not in all_children]
    if not root_links:
        raise ValueError("URDF has no root link (circular topology?)")

    # For a serial chain, follow parent → child:
    link_order: list[str] = []  # ordered list of moving links
    joint_order: list[dict] = []

    # Build adjacency: parent → list of (joint, child)
    adj: dict[str, list[dict]] = {}
    for j in joint_list:
        adj.setdefault(j["parent"], []).append(j)

    # BFS / DFS from root, collect non-fixed joints only
    name_to_idx: dict[str, int] = {}  # child link name → index in link_order

    def _visit(parent_name: str, parent_idx: int) -> None:
        for jdata in adj.get(parent_name, []):
            child = jdata["child"]
            if jdata["type"] in ("revolute", "prismatic"):
                idx = len(link_order)
                link_order.append(child)
                jdata["parent_idx"] = parent_idx
                joint_order.append(jdata)
                name_to_idx[child] = idx
                _visit(child, idx)
            else:
                # Fixed joint: recurse with same parent
                _visit(child, parent_idx)

    for root_link in root_links:
        _visit(root_link, -1)

    if not link_order:
        raise ValueError("No revolute/prismatic joints found in URDF")

    # ── assemble JointConfig / LinkConfig lists ────────────────────────────
    joint_configs = []
    link_configs = []

    for jdata, link_name in zip(joint_order, link_order, strict=True):
        jc = JointConfig(
            parent=jdata["parent_idx"],
            type=jdata["type"],
            axis=jdata["axis"],
            origin_xyz=jdata["origin_xyz"],
            origin_R=jdata["origin_R"],
        )
        ld = link_map[link_name]
        lc = LinkConfig(mass=ld["mass"], com=ld["com"], inertia=ld["inertia"])
        joint_configs.append(jc)
        link_configs.append(lc)

    return build_model(joint_configs, link_configs, gravity=gravity)
