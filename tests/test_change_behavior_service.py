import copy
import pytest
from unittest.mock import MagicMock, patch

from app.game.models.match import MatchState, Match
from app.game.models.match_participation import MatchParticipation
from app.game.models.ball import Ball
from app.services.match_service import change_player_behavior


@pytest.fixture
def setup_match():
    db = MagicMock()

    club = MagicMock()
    club.id = 1

    player = MagicMock()
    player.player_id = 10
    player.is_on_field = True
    player.current_behavior_id = 5

    opponent = MagicMock()
    opponent.player_id = 20
    opponent.current_behavior_id = 6

    participation_a = MagicMock()
    participation_a.club_id = 1
    participation_a.players = [player]

    participation_b = MagicMock()
    participation_b.club_id = 2
    participation_b.players = [opponent]

    match = MagicMock()
    match.state = MatchState.IN_PROGRESS
    match.participation_a = participation_a
    match.participation_b = participation_b

    return db, club, player, opponent, match


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_success(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    setup_match,
):
    db, club, player, opponent, match = setup_match

    mock_get_match.return_value = match
    mock_get_club.return_value = club
    mock_get_behavior.return_value = MagicMock(id=7)

    change_player_behavior(
        db=db,
        user_id=1,
        match_id=100,
        player_id=10,
        behavior_id=7,
    )

    assert player.current_behavior_id == 7
    assert opponent.current_behavior_id == 6

    mock_get_behavior.assert_called_once_with(
        db=db,
        club_id=1,
        behavior_id=7,
    )


@patch("app.services.match_service.get_match")
def test_change_behavior_match_not_found(mock_get_match):
    mock_get_match.return_value = None

    with pytest.raises(LookupError, match="Match not found"):
        change_player_behavior(
            db=MagicMock(),
            user_id=1,
            match_id=999,
            player_id=10,
            behavior_id=7,
        )


@patch("app.services.match_service.get_match")
def test_change_behavior_match_not_in_progress(
    mock_get_match,
    setup_match,
):
    db, _, player, _, match = setup_match

    match.state = MatchState.FINISHED
    mock_get_match.return_value = match

    with pytest.raises(ValueError, match="Match is not in progress"):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_user_not_participating(
    mock_get_match,
    mock_get_club,
    setup_match,
):
    db, club, player, _, match = setup_match

    club.id = 3

    mock_get_match.return_value = match
    mock_get_club.return_value = club

    with pytest.raises(
        PermissionError,
        match="User is not participating in this match",
    ):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_player_not_found(
    mock_get_match,
    mock_get_club,
    setup_match,
):
    db, club, player, _, match = setup_match

    mock_get_match.return_value = match
    mock_get_club.return_value = club

    with pytest.raises(
        LookupError,
        match="Player not found in user's team",
    ):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=999,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_substitute(
    mock_get_match,
    mock_get_club,
    setup_match,
):
    db, club, player, _, match = setup_match

    player.is_on_field = False

    mock_get_match.return_value = match
    mock_get_club.return_value = club

    with pytest.raises(ValueError, match="Player is not on the field"):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_not_available(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    setup_match,
):
    db, club, player, _, match = setup_match

    mock_get_match.return_value = match
    mock_get_club.return_value = club
    mock_get_behavior.return_value = None

    with pytest.raises(LookupError, match="Behavior not available"):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=999,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_multiple_changes(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    setup_match,
):
    db, club, player, _, match = setup_match

    mock_get_match.return_value = match
    mock_get_club.return_value = club
    mock_get_behavior.return_value = MagicMock()

    for behavior_id in [7, 8, 9]:
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=behavior_id,
        )

    assert player.current_behavior_id == 9
    assert mock_get_behavior.call_count == 3


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_team_b(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    setup_match,
):
    db, club, player, opponent, match = setup_match

    club.id = 2

    mock_get_match.return_value = match
    mock_get_club.return_value = club
    mock_get_behavior.return_value = MagicMock(id=7)

    change_player_behavior(
        db=db,
        user_id=2,
        match_id=100,
        player_id=20,
        behavior_id=7,
    )

    assert opponent.current_behavior_id == 7
    assert player.current_behavior_id == 5

    mock_get_behavior.assert_called_once_with(
        db=db,
        club_id=2,
        behavior_id=7,
    )


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_opponent_player(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    setup_match,
):
    db, club, player, opponent, match = setup_match

    mock_get_match.return_value = match
    mock_get_club.return_value = club

    with pytest.raises(
        LookupError,
        match="Player not found in user's team",
    ):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=20,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5
    assert opponent.current_behavior_id == 6

    mock_get_behavior.assert_not_called()


@patch("app.services.match_service.get_match")
def test_change_behavior_match_not_started(
    mock_get_match,
    setup_match,
):
    db, _, player, _, match = setup_match

    match.state = MatchState.NOT_STARTED
    mock_get_match.return_value = match

    with pytest.raises(
        ValueError,
        match="Match is not in progress",
    ):
        change_player_behavior(
            db=db,
            user_id=1,
            match_id=100,
            player_id=10,
            behavior_id=7,
        )

    assert player.current_behavior_id == 5


@patch("app.services.match_service.behavior_repository.get_available_by_id")
@patch("app.services.match_service.club_repository.get_by_user_id")
@patch("app.services.match_service.get_match")
def test_change_behavior_reflected_in_next_snapshot(
    mock_get_match,
    mock_get_club,
    mock_get_behavior,
    six_players,
):
    db = MagicMock()

    club = MagicMock()
    club.id = 1

    mock_get_club.return_value = club
    mock_get_behavior.return_value = MagicMock(id=7)

    players_a = copy.deepcopy(six_players)
    players_b = copy.deepcopy(six_players)

    # Ensure different player IDs for each team
    for player in players_b:
        player.player_id += 6

    # Assign initial behaviors
    for player in players_a:
        if player.is_on_field:
            player.current_behavior_id = 5

    for player in players_b:
        if player.is_on_field:
            player.current_behavior_id = 6

    match = Match(
        match_id=100,
        participation_a=MatchParticipation(
            club_id=1,
            roster_id=1,
            players=players_a,
        ),
        participation_b=MatchParticipation(
            club_id=2,
            roster_id=2,
            players=players_b,
        ),
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(0.0, 0.0),
        ),
        duration_ticks=100,
        state=MatchState.IN_PROGRESS,
    )

    mock_get_match.return_value = match

    player = next(
        p for p in players_a
        if p.is_on_field
    )

    previous_snapshot = match.snapshot()

    change_player_behavior(
        db=db,
        user_id=1,
        match_id=100,
        player_id=player.player_id,
        behavior_id=7,
    )

    next_snapshot = match.snapshot()

    previous_player = next(
        p for p in previous_snapshot.players_a
        if p.player_id == player.player_id
    )

    updated_player = next(
        p for p in next_snapshot.players_a
        if p.player_id == player.player_id
    )

    assert previous_player.current_behavior_id == 5
    assert updated_player.current_behavior_id == 7
    assert player.current_behavior_id == 7

    # Opponent's behavior remains unchanged
    assert next_snapshot.players_b[0].current_behavior_id == 6