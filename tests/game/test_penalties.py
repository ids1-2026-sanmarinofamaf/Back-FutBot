from unittest.mock import Mock

import pytest

from app.game.penalties import PenaltyShootout, PenaltySide


def make_shootout(seed=123, **overrides):
    data = {
        "club_a_id": 10,
        "club_b_id": 20,
        "kickers_a": (11, 12, 13),
        "kickers_b": (21, 22, 23),
        "seed": seed,
    }
    data.update(overrides)
    return PenaltyShootout(**data)


@pytest.fixture
def shootout():
    return make_shootout()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"club_b_id": 10}, "cannot play against itself"),
        ({"kickers_a": (11, 12)}, "exactly three"),
        ({"kickers_b": (21, 22, 23, 24)}, "exactly three"),
        ({"kickers_a": (11, 11, 13)}, "distinct"),
        ({"kickers_b": (21, 22, 22)}, "distinct"),
    ],
)
def test_reject_invalid_shootout(overrides, message):
    with pytest.raises(ValueError, match=message):
        make_shootout(**overrides)


@pytest.mark.parametrize(
    ("kick_side", "save_side", "expected_goal"),
    [
        (PenaltySide.LEFT, PenaltySide.LEFT, False),
        (PenaltySide.LEFT, PenaltySide.CENTER, True),
        (PenaltySide.LEFT, PenaltySide.RIGHT, True),
        (PenaltySide.CENTER, PenaltySide.LEFT, True),
        (PenaltySide.CENTER, PenaltySide.CENTER, False),
        (PenaltySide.CENTER, PenaltySide.RIGHT, True),
        (PenaltySide.RIGHT, PenaltySide.LEFT, True),
        (PenaltySide.RIGHT, PenaltySide.CENTER, True),
        (PenaltySide.RIGHT, PenaltySide.RIGHT, False),
    ],
)
def test_penalty_goal_depends_on_selected_sides(
    shootout,
    kick_side,
    save_side,
    expected_goal,
):
    result = shootout.resolve_penalty(kick_side, save_side)

    assert result["is_goal"] is expected_goal
    assert result["kick_side"] == kick_side.value
    assert result["save_side"] == save_side.value
    assert result["score_club_a"] == int(expected_goal)
    assert result["score_club_b"] == 0
    assert shootout.turn == 1
    assert shootout.winner_club_id is None


def test_shootout_alternates_clubs_and_uses_each_kicker_once(shootout):
    results = [
        shootout.resolve_penalty(PenaltySide.LEFT, PenaltySide.LEFT)
        for _ in range(6)
    ]

    assert [result["turn"] for result in results] == [1, 2, 3, 4, 5, 6]
    assert [result["club_id"] for result in results] == [
        10, 20, 10, 20, 10, 20,
    ]
    assert [result["kicker"] for result in results] == [
        11, 21, 12, 22, 13, 23,
    ]


@pytest.mark.parametrize(
    ("winner_id", "expected_score"),
    [
        (10, (3, 0)),
        (20, (0, 3)),
    ],
)
def test_winner_is_decided_after_all_six_penalties(
    shootout,
    winner_id,
    expected_score,
):
    for turn in range(6):
        kicking_club = 10 if turn % 2 == 0 else 20
        save_side = (
            PenaltySide.RIGHT
            if kicking_club == winner_id
            else PenaltySide.LEFT
        )

        shootout.resolve_penalty(PenaltySide.LEFT, save_side)

        if turn < 5:
            assert shootout.winner_club_id is None

    assert shootout.winner_club_id == winner_id
    assert (shootout.score_a, shootout.score_b) == expected_score


@pytest.mark.parametrize("chosen_winner", [10, 20])
def test_tied_shootout_uses_coin_toss(
    shootout,
    monkeypatch,
    chosen_winner,
):
    choice = Mock(return_value=chosen_winner)
    monkeypatch.setattr(shootout._rng, "choice", choice)

    for _ in range(6):
        shootout.resolve_penalty(PenaltySide.LEFT, PenaltySide.LEFT)

    choice.assert_called_once_with((10, 20))
    assert shootout.winner_club_id == chosen_winner
    assert (shootout.score_a, shootout.score_b) == (0, 0)


@pytest.mark.parametrize(
    ("kick_side", "save_side"),
    [
        (None, None),
        (PenaltySide.CENTER, None),
        (None, PenaltySide.RIGHT),
    ],
)
def test_same_seed_and_choices_produce_same_results(
    kick_side,
    save_side,
):
    first = make_shootout(seed=123)
    second = make_shootout(seed=123)
    unrelated = make_shootout(seed=999)

    for _ in range(6):
        first_result = first.resolve_penalty(kick_side, save_side)

        # Otra tanda no debe alterar el generador de estas dos.
        unrelated.resolve_penalty()

        second_result = second.resolve_penalty(kick_side, save_side)

        assert first_result == second_result
        assert first_result["kick_side"] in {"LEFT", "CENTER", "RIGHT"}
        assert first_result["save_side"] in {"LEFT", "CENTER", "RIGHT"}

        if kick_side is not None:
            assert first_result["kick_side"] == kick_side.value
        if save_side is not None:
            assert first_result["save_side"] == save_side.value

    assert first.winner_club_id == second.winner_club_id
    assert first.winner_club_id in (10, 20)


@pytest.mark.parametrize("invalid_side", ["LEFT", 0, object()])
@pytest.mark.parametrize("invalid_field", ["kick_side", "save_side"])
def test_invalid_side_does_not_change_state_or_random_generator(
    shootout,
    invalid_side,
    invalid_field,
):
    random_state = shootout._rng.getstate()

    with pytest.raises(ValueError, match="PenaltySide"):
        shootout.resolve_penalty(**{invalid_field: invalid_side})

    assert shootout.turn == 0
    assert (shootout.score_a, shootout.score_b) == (0, 0)
    assert shootout.winner_club_id is None
    assert shootout._rng.getstate() == random_state


def test_seventh_penalty_is_rejected_without_changes(shootout):
    for _ in range(6):
        shootout.resolve_penalty(PenaltySide.LEFT, PenaltySide.LEFT)

    winner = shootout.winner_club_id
    random_state = shootout._rng.getstate()

    with pytest.raises(ValueError, match="6 rounds"):
        shootout.resolve_penalty()

    assert shootout.turn == 6
    assert (shootout.score_a, shootout.score_b) == (0, 0)
    assert shootout.winner_club_id == winner
    assert shootout._rng.getstate() == random_state
