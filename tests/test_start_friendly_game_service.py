import asyncio

import pytest

from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
    call,
)

from app.models.friendly_game import FriendlyGameState
from app.models.friendly_game_participation import FriendlyGameRole

from app.services.friendly_game_service import (
    start_friendly_game,
    _finish_friendly_game,
    FriendlyGameNotFoundError,
    FriendlyGameForbiddenError,
)

from app.game.constants import FIELD_WIDTH, FIELD_HEIGHT


def make_participation(role):
    participation = MagicMock()
    participation.role = role
    return participation


def make_valid_friendly_game():
    creator_participation = make_participation(
        FriendlyGameRole.CREATOR
    )

    guest_participation = make_participation(
        FriendlyGameRole.GUEST
    )

    friendly_game = MagicMock()

    friendly_game.id = 10
    friendly_game.creator_id = 1
    friendly_game.duration = 1000
    friendly_game.state = FriendlyGameState.POR_COMENZAR
    friendly_game.participations = [
        creator_participation,
        guest_participation,
    ]

    return (
        friendly_game,
        creator_participation,
        guest_participation,
    )


@patch("app.services.friendly_game_service.start_match")
@patch("app.services.friendly_game_service.load_match_behaviors")
@patch("app.services.friendly_game_service._create_match_participation")
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_success(
    mock_friendly_game_repository,
    mock_club_repository,
    mock_create_match_participation,
    mock_load_match_behaviors,
    mock_start_match,
):
    db = MagicMock()

    (
        friendly_game,
        creator_participation,
        guest_participation,
    ) = make_valid_friendly_game()

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 1

    mock_club_repository.get_by_user_id.return_value = club

    match_participation_a = MagicMock()
    match_participation_b = MagicMock()

    mock_create_match_participation.side_effect = [
        match_participation_a,
        match_participation_b,
    ]

    behaviors = [MagicMock(), MagicMock()]

    mock_load_match_behaviors.return_value = behaviors
    mock_start_match.return_value = 50

    result = asyncio.run(
        start_friendly_game(
            db=db,
            friendly_game_id=10,
            user_id=5,
            requested_state=FriendlyGameState.JUGANDO,
        )
    )

    assert result == 50

    # both MatchParticipations were created
    assert mock_create_match_participation.call_count == 2

    mock_create_match_participation.assert_has_calls([
        call(
            db=db,
            friendly_participation=creator_participation,
            mirror_position=False,
        ),
        call(
            db=db,
            friendly_participation=guest_participation,
            mirror_position=True,
        ),
    ])

    # inspect the Match passed to start_match
    created_match = mock_start_match.call_args.kwargs["match"]

    assert (
        created_match.participation_a
        is match_participation_a
    )

    assert (
        created_match.participation_b
        is match_participation_b
    )

    assert created_match.duration_ticks == 1000

    # ball must start in the center and stopped
    assert created_match.ball.position == (
        FIELD_WIDTH / 2,
        FIELD_HEIGHT / 2,
    )

    assert created_match.ball.velocity == (0.0, 0.0)

    # behaviors were loaded for the match
    mock_load_match_behaviors.assert_called_once_with(
        db=db,
        match=created_match,
    )

    mock_start_match.assert_called_once()

    # FriendlyGame changes to JUGANDO
    mock_friendly_game_repository.update_state.assert_called_once_with(
        db=db,
        friendly_game=friendly_game,
        state=FriendlyGameState.JUGANDO,
    )

    db.commit.assert_called_once()

@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_not_found(
    mock_friendly_game_repository,
):
    db = MagicMock()

    mock_friendly_game_repository.get_by_id.return_value = None

    with pytest.raises(
        FriendlyGameNotFoundError,
        match="Friendly game not found",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=999,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )

    db.rollback.assert_called_once()

@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_rejects_non_host(
    mock_friendly_game_repository,
    mock_club_repository,
):
    db = MagicMock()

    friendly_game, _, _ = make_valid_friendly_game()

    friendly_game.creator_id = 1

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 2

    mock_club_repository.get_by_user_id.return_value = club

    with pytest.raises(
        FriendlyGameForbiddenError,
        match="Only the host can start the friendly game",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )

    db.rollback.assert_called_once()

@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_requires_two_participants(
    mock_friendly_game_repository,
    mock_club_repository,
):
    db = MagicMock()

    friendly_game, creator, _ = make_valid_friendly_game()

    friendly_game.participations = [creator]

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 1

    mock_club_repository.get_by_user_id.return_value = club

    with pytest.raises(
        FriendlyGameForbiddenError,
        match="Friendly game must have exactly two participants",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )

    db.rollback.assert_called_once()

@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_rejects_invalid_requested_state(
    mock_friendly_game_repository,
    mock_club_repository,
):
    db = MagicMock()

    friendly_game, _, _ = make_valid_friendly_game()

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 1

    mock_club_repository.get_by_user_id.return_value = club

    with pytest.raises(
        FriendlyGameForbiddenError,
        match="Invalid state transition",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.FINALIZADO,
            )
        )

@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_rejects_already_started_game(
    mock_friendly_game_repository,
    mock_club_repository,
):
    db = MagicMock()

    friendly_game, _, _ = make_valid_friendly_game()

    friendly_game.state = FriendlyGameState.JUGANDO

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 1

    mock_club_repository.get_by_user_id.return_value = club

    with pytest.raises(
        FriendlyGameForbiddenError,
        match="Friendly game cannot be started",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )


@patch("app.services.friendly_game_service.start_match")
@patch("app.services.friendly_game_service.load_match_behaviors")
@patch("app.services.friendly_game_service._create_match_participation")
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_start_friendly_game_restores_state_if_match_start_fails(
    mock_friendly_game_repository,
    mock_club_repository,
    mock_create_match_participation,
    mock_load_match_behaviors,
    mock_start_match,
):
    db = MagicMock()

    friendly_game, _, _ = make_valid_friendly_game()

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    club = MagicMock()
    club.id = 1

    mock_club_repository.get_by_user_id.return_value = club

    mock_create_match_participation.side_effect = [
        MagicMock(),
        MagicMock(),
    ]

    mock_load_match_behaviors.return_value = []

    mock_start_match.side_effect = RuntimeError(
        "Could not start match"
    )

    with pytest.raises(
        RuntimeError,
        match="Could not start match",
    ):
        asyncio.run(
            start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )

    assert (
        mock_friendly_game_repository.update_state.call_count
        == 2
    )

    mock_friendly_game_repository.update_state.assert_has_calls([
        call(
            db=db,
            friendly_game=friendly_game,
            state=FriendlyGameState.JUGANDO,
        ),
        call(
            db=db,
            friendly_game=friendly_game,
            state=FriendlyGameState.POR_COMENZAR,
        ),
    ])

    assert db.commit.call_count == 2

@patch("app.services.friendly_game_service.SessionLocal")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_finish_friendly_game_sets_finalizado(
    mock_friendly_game_repository,
    mock_session_local,
):
    db = MagicMock()

    context_manager = MagicMock()
    context_manager.__enter__.return_value = db
    context_manager.__exit__.return_value = None

    mock_session_local.return_value = context_manager

    friendly_game = MagicMock()
    friendly_game.id = 10

    mock_friendly_game_repository.get_by_id.return_value = (
        friendly_game
    )

    asyncio.run(
        _finish_friendly_game(
            friendly_game_id=10,
        )
    )

    mock_friendly_game_repository.update_state.assert_called_once_with(
        db=db,
        friendly_game=friendly_game,
        state=FriendlyGameState.FINALIZADO,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()