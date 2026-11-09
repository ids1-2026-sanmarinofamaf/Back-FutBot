from unittest.mock import MagicMock, patch

from app.game.active_matches import (
    active_matches,
    register_match,
    get_match,
)
from app.models.friendly_game import FriendlyGameState
from app.repositories.match_repository import get_next_match_id
from app.repositories.friendly_game_repository import (
    finalize_interrupted_games,
)
from app.services.startup_service import recover_interrupted_games


# verify that match IDs come from the database sequence.
def test_match_ids_are_generated_by_sequence():
    db = MagicMock()
    db.execute.return_value.scalar_one.side_effect = [50, 51]

    first_id = get_next_match_id(db)
    second_id = get_next_match_id(db)

    assert first_id == 50
    assert second_id == 51
    assert first_id != second_id
    assert db.execute.call_count == 2


# verify that matches remain in memory.
def test_matches_are_registered_in_memory():
    active_matches.clear()

    match = MagicMock()
    match.match_id = 100

    try:
        register_match(match)

        assert get_match(100) is match
        assert active_matches[100] is match
    finally:
        active_matches.clear()


# verify that interrupted games are finalized.
def test_interrupted_games_are_finalized():
    db = MagicMock()
    db.execute.return_value.rowcount = 2

    result = finalize_interrupted_games(db)

    assert result == 2
    db.execute.assert_called_once()

    statement = db.execute.call_args.args[0]
    params = statement.compile().params

    assert statement.table.name == "friendly_games"
    assert FriendlyGameState.JUGANDO in params.values()
    assert FriendlyGameState.FINALIZADO in params.values()


# verify that recovery commits changes on startup.
@patch("app.services.startup_service.SessionLocal")
@patch(
    "app.services.startup_service."
    "friendly_game_repository.finalize_interrupted_games"
)
def test_startup_recovers_interrupted_games(
    mock_finalize,
    mock_session_local,
):
    db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = db

    recover_interrupted_games()

    mock_finalize.assert_called_once_with(db)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# verify that IDs can continue after a simulated restart.
def test_match_ids_are_not_reused_after_restart():
    db = MagicMock()
    db.execute.return_value.scalar_one.side_effect = [100, 101]

    first_id = get_next_match_id(db)

    # simulate clearing runtime matches after a restart.
    active_matches.clear()

    second_id = get_next_match_id(db)

    assert second_id > first_id
