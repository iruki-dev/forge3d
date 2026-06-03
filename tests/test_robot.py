"""P7 tests: robot module, FK accuracy, World integration."""

from __future__ import annotations

import numpy as np
import pytest

import forge3d as f3d
import forge3d.robot as f3r
from forge3d.robot.robot import Robot, _rotation_from_z

# ── forge3d.robot.load ────────────────────────────────────────────────────────


class TestRobotLoad:
    def test_load_ur5(self):
        arm = f3r.load("ur5")
        assert isinstance(arm, Robot)
        assert arm.n_joints == 6
        assert arm.name == "ur5"

    def test_load_case_insensitive(self):
        arm = f3r.load("UR5")
        assert isinstance(arm, Robot)

    def test_load_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown robot"):
            f3r.load("r2d2")

    def test_default_joints_zero(self):
        arm = f3r.load("ur5")
        np.testing.assert_allclose(arm.q, np.zeros(6))


# ── Joint control ─────────────────────────────────────────────────────────────


class TestJointControl:
    def test_set_joint(self):
        arm = f3r.load("ur5")
        arm.set_joint(0, 1.5)
        assert arm.q[0] == pytest.approx(1.5)
        assert arm.q[1] == pytest.approx(0.0)  # others unchanged

    def test_set_joints(self):
        arm = f3r.load("ur5")
        q_target = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        arm.set_joints(q_target)
        np.testing.assert_allclose(arm.q, q_target)

    def test_q_setter(self):
        arm = f3r.load("ur5")
        arm.q = np.ones(6)
        np.testing.assert_allclose(arm.q, np.ones(6))

    def test_q_setter_wrong_shape(self):
        arm = f3r.load("ur5")
        with pytest.raises(ValueError):
            arm.q = np.ones(3)

    def test_set_joint_does_not_mutate_externally(self):
        arm = f3r.load("ur5")
        q_before = arm.q.copy()
        arm.set_joint(0, 1.0)
        assert q_before[0] == pytest.approx(0.0)  # external copy unchanged


# ── FK accuracy ───────────────────────────────────────────────────────────────


class TestFK:
    def test_ee_pose_returns_pos_and_rotation(self):
        arm = f3r.load("ur5")
        pos, R = arm.ee_pose()
        assert pos.shape == (3,)
        assert R.shape == (3, 3)

    def test_rotation_matrix_orthogonal(self):
        arm = f3r.load("ur5")
        arm.set_joints([0.5, -1.0, 0.3, -0.5, 0.2, 0.1])
        _, R = arm.ee_pose()
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-10)
        assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-8)

    def test_joint0_rotation_changes_ee(self):
        """Rotating joint 0 (base) should change EE x/y position."""
        arm = f3r.load("ur5")
        arm.set_joints([-np.pi / 2, -np.pi / 2, 0, -np.pi / 2, 0, 0])
        pos0, _ = arm.ee_pose()
        arm.set_joint(0, np.pi / 2)  # rotate base by π
        pos1, _ = arm.ee_pose()
        # EE should have moved in XY plane
        assert np.linalg.norm(pos0[:2] - pos1[:2]) > 0.1

    def test_zero_config_ee_height(self):
        """At q=0 the EE should be above the base (z > 0 or near base height)."""
        arm = f3r.load("ur5")
        pos, _ = arm.ee_pose()
        # UR5 at q=0 extends horizontally; EE height near base height
        total_reach = 0.4250 + 0.3922 + 0.1093 + 0.0950 + 0.0823
        ee_dist = float(np.linalg.norm(pos))
        assert ee_dist < total_reach + 0.2, f"EE too far: {ee_dist:.3f}"

    def test_link_world_poses_count(self):
        arm = f3r.load("ur5")
        poses = arm.link_world_poses()
        assert len(poses) == 6

    def test_link_world_poses_orthogonal_rotations(self):
        arm = f3r.load("ur5")
        arm.set_joints([0.1, -0.5, 0.2, -0.3, 0.1, 0.0])
        for i, (pos, R) in enumerate(arm.link_world_poses()):
            assert pos.shape == (3,), f"link {i} pos shape wrong"
            np.testing.assert_allclose(
                R @ R.T, np.eye(3), atol=1e-10, err_msg=f"link {i} R not orthogonal"
            )


# ── Visual boxes ──────────────────────────────────────────────────────────────


class TestLinkVisualBoxes:
    def test_count(self):
        arm = f3r.load("ur5")
        boxes = arm.link_visual_boxes()
        assert len(boxes) == 6

    def test_half_extents_positive(self):
        arm = f3r.load("ur5")
        for i, (_c, _r, he) in enumerate(arm.link_visual_boxes()):
            assert np.all(he > 0), f"link {i} has non-positive half_extents"

    def test_rotation_matrix_in_box(self):
        arm = f3r.load("ur5")
        for i, (_c, R, _he) in enumerate(arm.link_visual_boxes()):
            np.testing.assert_allclose(
                R @ R.T, np.eye(3), atol=1e-10, err_msg=f"box {i} R not orthogonal"
            )

    def test_boxes_update_on_joint_change(self):
        arm = f3r.load("ur5")
        boxes_before = arm.link_visual_boxes()
        arm.set_joint(0, np.pi / 2)
        boxes_after = arm.link_visual_boxes()
        # At least link 0's center should differ
        assert not np.allclose(boxes_before[0][0], boxes_after[0][0]) or not np.allclose(
            boxes_before[1][0], boxes_after[1][0]
        )


# ── World integration ─────────────────────────────────────────────────────────


class TestWorldIntegration:
    def test_add_robot_creates_bodies(self):
        world = f3d.World()
        arm = f3r.load("ur5")
        world.add(arm)
        assert len(arm._body_ids) == 6

    def test_snapshot_includes_robot_links(self):
        world = f3d.World()
        world.add_ground()
        arm = f3r.load("ur5")
        world.add(arm)
        snap = world.snapshot()
        # ground + 6 links = 7
        assert len(snap.bodies) == 7

    def test_step_syncs_robot_links(self):
        world = f3d.World()
        arm = f3r.load("ur5")
        world.add(arm)
        world.step()
        # After step, body poses should match FK
        boxes = arm.link_visual_boxes()
        for bid, (center, _R, _) in zip(arm._body_ids, boxes, strict=True):
            b = next(b for b in world._physics._bodies if b.body_id == bid)
            np.testing.assert_allclose(b.pos, center, atol=1e-10)

    def test_robot_joint_change_reflected_in_snapshot(self):
        world = f3d.World()
        arm = f3r.load("ur5")
        world.add(arm)
        world.step()
        snap_before = world.snapshot()

        arm.set_joint(0, np.pi / 2)
        world.step()
        snap_after = world.snapshot()

        # Link body positions should differ between snapshots
        pos_before = np.array([b.transform.position for b in snap_before.bodies if "ur5" in b.name])
        pos_after = np.array([b.transform.position for b in snap_after.bodies if "ur5" in b.name])
        assert not np.allclose(pos_before, pos_after), (
            "Robot link positions did not update after joint change"
        )

    def test_robot_and_dynamic_body_coexist(self):
        world = f3d.World()
        world.add_ground()
        arm = f3r.load("ur5")
        world.add(arm)
        ball = world.add_sphere(radius=0.2, position=(2, 0, 3))
        for _ in range(30):
            world.step(dt=1 / 60)
        # Ball should have fallen (gravity), robot should be static
        assert ball.position[2] < 3.0  # ball fell

    def test_repr_after_add(self):
        world = f3d.World()
        arm = f3r.load("ur5")
        world.add(arm)
        assert "Robot" in repr(arm)


# ── Helpers ───────────────────────────────────────────────────────────────────


class TestRotationFromZ:
    def test_z_aligned(self):
        R = _rotation_from_z(np.array([0.0, 0.0, 1.0]))
        np.testing.assert_allclose(R[:, 2], [0, 0, 1], atol=1e-10)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-10)

    def test_arbitrary_direction(self):
        z = np.array([0.3, -0.5, 0.8])
        z /= np.linalg.norm(z)
        R = _rotation_from_z(z)
        np.testing.assert_allclose(R[:, 2], z, atol=1e-10)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-10)
        assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-8)
