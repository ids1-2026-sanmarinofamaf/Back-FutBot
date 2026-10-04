import pytest

from app.game.models.behavior_definition import BehaviorDefinition


def test_behavior_definition_stores_id_and_code():
    behavior = BehaviorDefinition(
        id=1,
        code="def play():\n    return wait()",
    )

    assert behavior.id == 1
    assert behavior.code == "def play():\n    return wait()"


def test_behavior_definition_is_immutable():
    behavior = BehaviorDefinition(
        id=1,
        code="def play():\n    return wait()",
    )

    with pytest.raises(Exception):
        behavior.code = "new code"