"""FORGE RUNNER — entry point.

Run the game (opens a real window):

    python main.py

Headless smoke test (no window; verifies the whole stack and saves
screenshots — handy on CI or servers):

    python main.py --smoke 420
"""

from __future__ import annotations

import argparse
import sys

import hud
import settings as S
from camera_rig import CameraRig
from game import DEAD, MENU, PLAYING, WIN, Game

import forge3d as f3d


def build() -> tuple[f3d.World, Game, CameraRig]:
    world = f3d.World(gravity=S.GRAVITY)
    game = Game(world)
    rig = CameraRig(world, game.player.position)
    return world, game, rig


# ──────────────────────────────────────────────────────────────────────────
def run_windowed() -> None:
    world, game, rig = build()
    viewer = f3d.Viewer(
        world,
        width=S.WIDTH,
        height=S.HEIGHT,
        title=S.TITLE,
        fps=60,
        shadow_resolution=S.SHADOW_RESOLUTION,
        sky_color=S.SKY_COLOR,
        show_grid=False,
    )
    while viewer.is_open:
        inp = viewer.input
        dt = min(viewer.dt, S.MAX_DT)

        rig.update(inp, dt, game.player.position)
        game.update(inp, dt, rig.cam)
        world.step(dt, substeps=S.PHYSICS_SUBSTEPS)

        viewer.set_camera(rig.snapshot())
        viewer.draw()

        if game.state == MENU:
            hud.draw_menu(viewer)
        elif game.state == PLAYING:
            hud.draw_playing(viewer, game, game.player)
        elif game.state == DEAD:
            hud.draw_dead(viewer, game)
        elif game.state == WIN:
            hud.draw_win(viewer, game)
    viewer.close()


# ──────────────────────────────────────────────────────────────────────────
def run_smoke(frames: int) -> None:
    import imageio.v2 as iio

    world, game, rig = build()
    viewer = f3d.Viewer(world, width=960, height=540, max_frames=frames + 10)
    inp = f3d.ScriptedInput()
    dt = 1 / 60
    shots = {1, frames // 3, 2 * frames // 3, frames - 1}

    for i in range(frames):
        inp.end_frame()
        if i == 5:
            inp.press(f3d.Key.ENTER)
        elif i >= 20:
            inp.hold(f3d.Key.W)
            if i % 70 == 0:
                inp.press(f3d.Key.SPACE)
            if i % 150 == 5:
                inp.press(f3d.Key.SHIFT)

        rig.update(inp, dt, game.player.position)
        game.update(inp, dt, rig.cam)
        world.step(dt, substeps=S.PHYSICS_SUBSTEPS)
        viewer.set_camera(rig.snapshot())
        frame = viewer.draw()
        if i in shots and frame is not None:
            iio.imwrite(f"smoke_{i:04d}.png", frame)

    p = game.player.position
    print(
        f"[smoke] OK — {frames} frames, state={game.state}, "
        f"player=({p[0]:.1f},{p[1]:.1f},{p[2]:.1f}), "
        f"hp={game.player.hp}, cores={game.cores_collected}, "
        f"score={game.score}, bodies={len(world.bodies)}"
    )


# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FORGE RUNNER")
    ap.add_argument(
        "--smoke",
        type=int,
        metavar="N",
        help="run N headless frames with scripted input, then exit",
    )
    args = ap.parse_args()
    if args.smoke:
        run_smoke(args.smoke)
    else:
        try:
            run_windowed()
        except Exception:
            print(
                "Could not open a window. On a headless machine, try:\n"
                "    python main.py --smoke 300",
                file=sys.stderr,
            )
            raise
