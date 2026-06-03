"""forge3d input system — keyboard and mouse state snapshots.

Usage::

    viewer = f3d.Viewer(world)
    while viewer.is_open:
        inp = viewer.input          # per-frame Input snapshot
        if inp.key_pressed(f3d.Key.SPACE):
            world.apply_impulse(ball, (0, 0, 8))
        if inp.key_held(f3d.Key.RIGHT):
            world.apply_impulse(ball, (3 * dt, 0, 0))
        world.step()
        viewer.draw()
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Key constants ─────────────────────────────────────────────────────────────


class Key:
    """Keyboard key name constants.

    All values are lowercase strings that match the names used internally by
    the viewer's event back-end.  Pass them to :meth:`Input.key_held` etc.

    Examples::

        inp.key_held(f3d.Key.SPACE)
        inp.key_pressed('w')         # raw strings work too
    """

    # Letters
    A = "a"; B = "b"; C = "c"; D = "d"; E = "e"  # noqa: E702
    F = "f"; G = "g"; H = "h"; I = "i"; J = "j"  # noqa: E702,E741
    K = "k"; L = "l"; M = "m"; N = "n"; O = "o"  # noqa: E702,E741
    P = "p"; Q = "q"; R = "r"; S = "s"; T = "t"  # noqa: E702
    U = "u"; V = "v"; W = "w"; X = "x"; Y = "y"  # noqa: E702
    Z = "z"

    # Digits (prefixed to avoid clashing with int literals)
    N0 = "0"; N1 = "1"; N2 = "2"; N3 = "3"; N4 = "4"  # noqa: E702
    N5 = "5"; N6 = "6"; N7 = "7"; N8 = "8"; N9 = "9"  # noqa: E702

    # Special
    SPACE = "space"
    ESCAPE = "escape"
    ENTER = "enter"
    RETURN = "enter"        # alias
    BACKSPACE = "backspace"
    DELETE = "delete"
    TAB = "tab"
    INSERT = "insert"

    # Arrow keys
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    # Page / Home / End
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"
    HOME = "home"
    END = "end"

    # Modifier keys (these appear in key events, not as held-state modifiers)
    SHIFT = "shift"
    CTRL = "ctrl"
    ALT = "alt"
    SUPER = "super"       # Windows/Command key

    # Function keys
    F1 = "f1"; F2 = "f2"; F3 = "f3"; F4 = "f4"    # noqa: E702
    F5 = "f5"; F6 = "f6"; F7 = "f7"; F8 = "f8"    # noqa: E702
    F9 = "f9"; F10 = "f10"; F11 = "f11"; F12 = "f12"  # noqa: E702

    # Numpad
    KP0 = "kp0"; KP1 = "kp1"; KP2 = "kp2"; KP3 = "kp3"; KP4 = "kp4"  # noqa: E702
    KP5 = "kp5"; KP6 = "kp6"; KP7 = "kp7"; KP8 = "kp8"; KP9 = "kp9"  # noqa: E702
    KP_ENTER = "kp_enter"
    KP_PLUS = "kp_plus"
    KP_MINUS = "kp_minus"
    KP_MULTIPLY = "kp_multiply"
    KP_DIVIDE = "kp_divide"


# ── Immutable per-frame snapshot ──────────────────────────────────────────────


@dataclass(frozen=True)
class Input:
    """Immutable snapshot of input state for a single rendered frame.

    Created by the viewer's event loop; passed to ``@app.on_update`` and
    available via ``viewer.input`` after each :meth:`Viewer.draw` call.

    All keys are plain strings — use :class:`Key` constants or raw lowercase
    strings (``'w'``, ``'space'``, ``'f1'``).

    Mouse buttons: ``0`` = left, ``1`` = right, ``2`` = middle.
    """

    _keys_held: frozenset[str] = field(default_factory=frozenset)
    _keys_pressed: frozenset[str] = field(default_factory=frozenset)
    _keys_released: frozenset[str] = field(default_factory=frozenset)
    _mouse_pos: tuple[float, float] = (0.0, 0.0)
    _mouse_delta: tuple[float, float] = (0.0, 0.0)
    _mouse_buttons: frozenset[int] = field(default_factory=frozenset)
    _scroll_delta: float = 0.0

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def key_held(self, key: str) -> bool:
        """True while the key is physically held down."""
        return key in self._keys_held

    def key_pressed(self, key: str) -> bool:
        """True only during the first frame the key was pressed."""
        return key in self._keys_pressed

    def key_released(self, key: str) -> bool:
        """True only during the first frame the key was released."""
        return key in self._keys_released

    def any_key_held(self, *keys: str) -> bool:
        """True if *any* of the given keys are held."""
        return any(k in self._keys_held for k in keys)

    def all_keys_held(self, *keys: str) -> bool:
        """True if *all* of the given keys are held simultaneously."""
        return all(k in self._keys_held for k in keys)

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mouse_pos(self) -> tuple[float, float]:
        """Current cursor position in pixels `(x, y)` from top-left."""
        return self._mouse_pos

    def mouse_delta(self) -> tuple[float, float]:
        """Cursor movement since last frame `(dx, dy)` in pixels."""
        return self._mouse_delta

    def mouse_button(self, button: int = 0) -> bool:
        """True while the given mouse button is held (0=left, 1=right, 2=mid)."""
        return button in self._mouse_buttons

    def scroll_delta(self) -> float:
        """Mouse wheel scroll this frame (positive = scroll up / zoom in)."""
        return self._scroll_delta

    def __repr__(self) -> str:
        held = sorted(self._keys_held)
        return (
            f"Input(held={held}, "
            f"pos={self._mouse_pos}, "
            f"scroll={self._scroll_delta:+.1f})"
        )


# ── Empty singleton — returned when no windowing is available ─────────────────

EMPTY_INPUT: Input = Input()


# ── Mutable builder — used internally by Viewer ───────────────────────────────


class _InputBuilder:
    """Mutable input accumulator owned by the Viewer event loop.

    Call :meth:`build` to get an immutable :class:`Input` snapshot, then
    :meth:`end_frame` to reset per-frame state (pressed / released / scroll).
    """

    __slots__ = (
        "_keys_held",
        "_keys_pressed",
        "_keys_released",
        "_mouse_pos",
        "_prev_mouse_pos",
        "_mouse_buttons",
        "_scroll_accum",
    )

    def __init__(self) -> None:
        self._keys_held: set[str] = set()
        self._keys_pressed: set[str] = set()
        self._keys_released: set[str] = set()
        self._mouse_pos: tuple[float, float] = (0.0, 0.0)
        self._prev_mouse_pos: tuple[float, float] = (0.0, 0.0)
        self._mouse_buttons: set[int] = set()
        self._scroll_accum: float = 0.0

    # ── Event handlers (called by the windowing layer) ────────────────────────

    def on_key_down(self, key: str) -> None:
        key = key.lower()
        self._keys_held.add(key)
        self._keys_pressed.add(key)

    def on_key_up(self, key: str) -> None:
        key = key.lower()
        self._keys_held.discard(key)
        self._keys_released.add(key)

    def on_mouse_move(self, x: float, y: float) -> None:
        self._prev_mouse_pos = self._mouse_pos
        self._mouse_pos = (x, y)

    def on_mouse_down(self, button: int) -> None:
        self._mouse_buttons.add(button)

    def on_mouse_up(self, button: int) -> None:
        self._mouse_buttons.discard(button)

    def on_scroll(self, delta: float) -> None:
        self._scroll_accum += delta

    # ── Frame lifecycle ───────────────────────────────────────────────────────

    def build(self) -> Input:
        """Return an immutable :class:`Input` for the current frame."""
        dx = self._mouse_pos[0] - self._prev_mouse_pos[0]
        dy = self._mouse_pos[1] - self._prev_mouse_pos[1]
        return Input(
            _keys_held=frozenset(self._keys_held),
            _keys_pressed=frozenset(self._keys_pressed),
            _keys_released=frozenset(self._keys_released),
            _mouse_pos=self._mouse_pos,
            _mouse_delta=(dx, dy),
            _mouse_buttons=frozenset(self._mouse_buttons),
            _scroll_delta=self._scroll_accum,
        )

    def end_frame(self) -> None:
        """Clear per-frame events; call after each :meth:`Viewer.draw`."""
        self._keys_pressed.clear()
        self._keys_released.clear()
        self._scroll_accum = 0.0
        self._prev_mouse_pos = self._mouse_pos
