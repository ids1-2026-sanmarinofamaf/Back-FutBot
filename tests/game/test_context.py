"""
Unit tests for behavior execution context
"""

import pytest

from app.game.context import (
    get_current_context,
    set_current_context,
    clear_current_context,
)


def test_get_current_context_returns_set_context(context):
    set_current_context(context)

    assert get_current_context() is context

    clear_current_context()


def test_get_current_context_raises_when_context_is_not_set():
    clear_current_context()

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set",
    ):
        get_current_context()


def test_clear_current_context_removes_current_context(context):
    set_current_context(context)
    clear_current_context()

    with pytest.raises(
        RuntimeError,
        match="Behavior context is not set",
    ):
        get_current_context()

def test_set_current_context_remplace_previous_context(
        context, 
        other_context,
):
    set_current_context(context)
    set_current_context(other_context)

    assert get_current_context() is other_context

    clear_current_context()