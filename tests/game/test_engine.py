import pytest
from dataclasses import replace

from app.game.engine import GameEngine
from app.game.models.actions import MoveAction, WaitAction


def test_validate_actions_accepts_one_action_per_on_field_player(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    engine._validate_actions(
        match_snapshot,
        actions,
    )


def test_validate_actions_rejects_missing_action(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    actions.pop(next(iter(actions)))

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


def test_validate_actions_rejects_unexpected_player(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    substitute = next(
        player
        for player in match_snapshot.players_a
        if not player.is_on_field
    )

    actions[substitute.player_id] = WaitAction()

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


def test_validate_actions_rejects_invalid_action(
    match_snapshot,
):
    engine = GameEngine()

    actions = {
        player.player_id: WaitAction()
        for player in match_snapshot.players_a + match_snapshot.players_b
        if player.is_on_field
    }

    player_id = next(iter(actions))
    actions[player_id] = "invalid"

    with pytest.raises(ValueError):
        engine._validate_actions(
            match_snapshot,
            actions,
        )


from dataclasses import replace


def test_validate_actions_rejects_snapshot_without_six_on_field_players(
    match_snapshot,
):
    engine = GameEngine()

    player_out = replace(
        match_snapshot.players_a[0],
        is_on_field=False,
    )

    modified_snapshot = replace(
        match_snapshot,
        players_a=(
            player_out,
            *match_snapshot.players_a[1:],
        ),
    )

    actions = {
        player.player_id: WaitAction()
        for player in modified_snapshot.players_a + modified_snapshot.players_b
        if player.is_on_field
    }

    with pytest.raises(ValueError):
        engine._validate_actions(
            modified_snapshot,
            actions,
        )