"""FORGE RUNNER — HUD overlays (anchor-based, no manual pixel math)."""

from __future__ import annotations

import settings as S


def _hp_bar(hp: int, width: int = 20) -> str:
    filled = round(width * hp / S.MAX_HP)
    return "#" * filled + "-" * (width - filled)


def draw_playing(viewer, game, player) -> None:
    mins, secs = divmod(int(game.time), 60)
    viewer.draw_text(f"TIME {mins:02d}:{secs:02d}   SCORE {game.score}", anchor="topleft", size=22)
    viewer.draw_text(
        f"CORES {game.cores_collected}/{game.cores_total}",
        anchor="topleft",
        y=40,
        size=22,
        color=(1.0, 0.85, 0.2),
    )

    hp_col = (
        (0.3, 1.0, 0.4)
        if player.hp > 50
        else (1.0, 0.8, 0.2)
        if player.hp > 25
        else (1.0, 0.25, 0.2)
    )
    try:
        viewer.draw_rect(12, 74, 220, 16, (0.1, 0.1, 0.12), 0.7)
        viewer.draw_rect(14, 76, int(216 * player.hp / S.MAX_HP), 12, hp_col, 0.95)
    except Exception:
        viewer.draw_text(
            f"HP [{_hp_bar(player.hp)}]", anchor="topleft", y=70, size=20, color=hp_col
        )
    viewer.draw_text(str(player.hp), x=240, y=72, size=18, color=hp_col)

    dash = "DASH READY" if player.dash_cooldown <= 0 else f"DASH {player.dash_cooldown:.1f}s"
    viewer.draw_text(
        dash,
        anchor="topright",
        size=20,
        color=(0.4, 0.9, 1.0) if player.dash_cooldown <= 0 else (0.6, 0.6, 0.6),
    )
    if player.gliding:
        viewer.draw_text("GLIDING", anchor="topright", y=40, size=18, color=(0.7, 0.9, 1.0))

    if game.all_cores and not game.won:
        viewer.draw_text(
            "GATE OPEN — reach the extraction gate!",
            anchor="topcenter",
            y=70,
            size=24,
            color=(0.3, 1.0, 0.5),
        )
    if game.message_timer > 0:
        viewer.draw_text(
            game.message,
            anchor="center",
            y=viewer._height // 2 - 120,
            size=26,
            color=(1.0, 0.95, 0.6),
        )


def draw_menu(viewer) -> None:
    viewer.draw_text(
        "F O R G E   R U N N E R",
        anchor="center",
        y=viewer._height // 2 - 130,
        size=52,
        color=(1.0, 0.8, 0.2),
    )
    viewer.draw_text(
        "Collect 5 energy cores, then escape through the gate",
        anchor="center",
        y=viewer._height // 2 - 70,
        size=22,
    )
    viewer.draw_text(
        "WASD move   SPACE jump / double-jump / hold to glide",
        anchor="center",
        y=viewer._height // 2 - 10,
        size=20,
        color=(0.8, 0.9, 1.0),
    )
    viewer.draw_text(
        "SHIFT dash   Q/E + right-drag camera   wheel zoom",
        anchor="center",
        y=viewer._height // 2 + 20,
        size=20,
        color=(0.8, 0.9, 1.0),
    )
    viewer.draw_text(
        "Beware lava and the magenta sentries...",
        anchor="center",
        y=viewer._height // 2 + 60,
        size=18,
        color=(1.0, 0.5, 0.4),
    )
    viewer.draw_text(
        "PRESS ENTER TO START",
        anchor="center",
        y=viewer._height // 2 + 120,
        size=28,
        color=(0.3, 1.0, 0.5),
    )


def draw_dead(viewer, game) -> None:
    viewer.draw_text(
        "YOU ARE DOWN", anchor="center", y=viewer._height // 2 - 40, size=48, color=(1.0, 0.25, 0.2)
    )
    viewer.draw_text(
        f"Score so far: {game.score}", anchor="center", y=viewer._height // 2 + 10, size=24
    )
    viewer.draw_text(
        "Press ENTER to retry from your last checkpoint",
        anchor="center",
        y=viewer._height // 2 + 55,
        size=22,
        color=(0.8, 0.9, 1.0),
    )


def draw_win(viewer, game) -> None:
    mins, secs = divmod(int(game.time), 60)
    viewer.draw_text(
        "EXTRACTION COMPLETE!",
        anchor="center",
        y=viewer._height // 2 - 60,
        size=48,
        color=(0.3, 1.0, 0.5),
    )
    viewer.draw_text(
        f"Time {mins:02d}:{secs:02d}    Final score {game.score}",
        anchor="center",
        y=viewer._height // 2,
        size=28,
        color=(1.0, 0.85, 0.2),
    )
    viewer.draw_text("Press ESC to exit", anchor="center", y=viewer._height // 2 + 50, size=22)
