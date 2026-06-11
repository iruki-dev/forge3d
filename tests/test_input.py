"""Tests for forge3d.input — Key constants, Input snapshot, _InputBuilder."""

from __future__ import annotations

import pytest

from forge3d.input import EMPTY_INPUT, Key, _InputBuilder


class TestKey:
    def test_letter_constants(self):
        assert Key.A == "a"
        assert Key.Z == "z"
        assert Key.W == "w"

    def test_special_constants(self):
        assert Key.SPACE == "space"
        assert Key.ESCAPE == "escape"
        assert Key.ENTER == "enter"
        assert Key.RETURN == "enter"  # alias

    def test_arrow_constants(self):
        assert Key.UP == "up"
        assert Key.DOWN == "down"
        assert Key.LEFT == "left"
        assert Key.RIGHT == "right"

    def test_function_keys(self):
        assert Key.F1 == "f1"
        assert Key.F12 == "f12"

    def test_digit_constants(self):
        assert Key.N0 == "0"
        assert Key.N9 == "9"


class TestInputEmpty:
    def test_empty_input_all_false(self):
        inp = EMPTY_INPUT
        assert not inp.key_held("space")
        assert not inp.key_pressed("a")
        assert not inp.key_released("b")
        assert not inp.mouse_button(0)
        assert inp.mouse_pos() == (0.0, 0.0)
        assert inp.mouse_delta() == (0.0, 0.0)
        assert inp.scroll_delta() == 0.0

    def test_empty_input_is_immutable(self):
        inp = EMPTY_INPUT
        with pytest.raises((AttributeError, TypeError)):
            inp._keys_held = frozenset({"space"})  # type: ignore[misc]


class TestInputBuilder:
    def test_key_down_held_and_pressed(self):
        builder = _InputBuilder()
        builder.on_key_down("space")
        inp = builder.build()
        assert inp.key_held("space")
        assert inp.key_pressed("space")
        assert not inp.key_released("space")

    def test_key_up_released_not_held(self):
        builder = _InputBuilder()
        builder.on_key_down("a")
        builder.end_frame()
        builder.on_key_up("a")
        inp = builder.build()
        assert not inp.key_held("a")
        assert not inp.key_pressed("a")
        assert inp.key_released("a")

    def test_key_held_across_frames(self):
        builder = _InputBuilder()
        builder.on_key_down("w")
        builder.end_frame()
        inp = builder.build()
        # After end_frame: held stays, pressed cleared
        assert inp.key_held("w")
        assert not inp.key_pressed("w")

    def test_end_frame_clears_per_frame_state(self):
        builder = _InputBuilder()
        builder.on_key_down("space")
        builder.on_key_up("a")
        builder.on_scroll(1.0)
        builder.end_frame()
        inp = builder.build()
        assert not inp.key_pressed("space")
        assert not inp.key_released("a")
        assert inp.scroll_delta() == 0.0

    def test_mouse_position(self):
        builder = _InputBuilder()
        builder.on_mouse_move(100.0, 200.0)
        inp = builder.build()
        assert inp.mouse_pos() == (100.0, 200.0)

    def test_mouse_delta(self):
        builder = _InputBuilder()
        builder.on_mouse_move(0.0, 0.0)
        builder.end_frame()
        builder.on_mouse_move(10.0, -5.0)
        inp = builder.build()
        dx, dy = inp.mouse_delta()
        assert dx == pytest.approx(10.0)
        assert dy == pytest.approx(-5.0)

    def test_mouse_button(self):
        builder = _InputBuilder()
        builder.on_mouse_down(0)   # left
        builder.on_mouse_down(1)   # right
        inp = builder.build()
        assert inp.mouse_button(0)
        assert inp.mouse_button(1)
        assert not inp.mouse_button(2)

        builder.on_mouse_up(0)
        inp2 = builder.build()
        assert not inp2.mouse_button(0)
        assert inp2.mouse_button(1)

    def test_scroll_accumulation(self):
        builder = _InputBuilder()
        builder.on_scroll(1.0)
        builder.on_scroll(0.5)
        inp = builder.build()
        assert inp.scroll_delta() == pytest.approx(1.5)

    def test_any_key_held(self):
        builder = _InputBuilder()
        builder.on_key_down("a")
        inp = builder.build()
        assert inp.any_key_held("a", "b", "c")
        assert not inp.any_key_held("b", "c")

    def test_all_keys_held(self):
        builder = _InputBuilder()
        builder.on_key_down("ctrl")
        builder.on_key_down("s")
        inp = builder.build()
        assert inp.all_keys_held("ctrl", "s")
        assert not inp.all_keys_held("ctrl", "s", "shift")

    def test_key_normalised_to_lowercase(self):
        builder = _InputBuilder()
        builder.on_key_down("A")   # uppercase
        inp = builder.build()
        assert inp.key_held("a")
        assert not inp.key_held("A")

    def test_repr(self):
        builder = _InputBuilder()
        builder.on_key_down("space")
        inp = builder.build()
        r = repr(inp)
        assert "space" in r
