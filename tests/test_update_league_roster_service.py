
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.league import LeagueState
from app.models.player_on_roster import PlayerOnRoster, RosterSlot
from app.models.roster import Formation, Roster
from app.schemas.roster import RosterCreate
from app.services.league_service import (
    InvalidLeagueState,
    InvalidRoster,
    LeagueForbidden,
    LeagueNotFound,
    get_league_roster,
    update_league_roster,
)

from app.services import league_runner
from app.models.match_participation import MatchRole

LEAGUE_ID = 10
USER_ID = 20
CLUB_ID = 30
ROSTER_ID = 40


def make_roster():
    roster = Roster(
        id=ROSTER_ID,
        club_id=CLUB_ID,
        formation=Formation.DEFENSIVE,
    )

    slots = [
        RosterSlot.LEFT,
        RosterSlot.CENTER,
        RosterSlot.RIGHT,
    ]

    roster.players = [
        PlayerOnRoster(
            player_id=i + 1,
            is_starter=i < 3,
            slot=slots[i] if i < 3 else None,
            initial_behavior_id=1 if i < 3 else None,
        )
        for i in range(6)
    ]

    return roster


def make_payload():
    # keep the same players, but swap 1 with 4
    return RosterCreate(
        formation=Formation.OFFENSIVE,
        players=[
            {
                "player_id": 1,
                "is_starter": False,
                "slot": None,
                "initial_behavior_id": None,
            },
            {
                "player_id": 2,
                "is_starter": True,
                "slot": "left",
                "initial_behavior_id": 1,
            },
            {
                "player_id": 3,
                "is_starter": True,
                "slot": "center",
                "initial_behavior_id": 1,
            },
            {
                "player_id": 4,
                "is_starter": True,
                "slot": "right",
                "initial_behavior_id": 1,
            },
            {
                "player_id": 5,
                "is_starter": False,
                "slot": None,
                "initial_behavior_id": None,
            },
            {
                "player_id": 6,
                "is_starter": False,
                "slot": None,
                "initial_behavior_id": None,
            },
        ],
    )


@pytest.fixture
def setup_repositories():
    db = MagicMock()
    roster = make_roster()

    league = SimpleNamespace(
        id=LEAGUE_ID,
        state=LeagueState.INICIADA,
    )

    club = SimpleNamespace(id=CLUB_ID)

    participation = SimpleNamespace(roster=roster)

    with (
        patch(
            "app.services.league_service.league_repository.get_by_id",
            return_value=league,
        ) as mock_get_league,
        patch(
            "app.services.league_service.club_repository.get_by_user_id",
            return_value=club,
        ) as mock_get_club,
        patch(
            "app.services.league_service.league_participation_repository.get_participation_by_club_and_league",
            return_value=participation,
        ) as mock_get_participation,
        patch(
            "app.services.league_service.behavior_repository.get_by_id",
            return_value=SimpleNamespace(
                id=1,
                is_default=True,
                club_id=None,
            ),
        ) as mock_get_behavior,
        patch(
            "app.services.league_service.validate_coach_behavior",
        ) as mock_validate_coach,
    ):
        yield SimpleNamespace(
            db=db,
            roster=roster,
            league=league,
            club=club,
            participation=participation,
            get_league=mock_get_league,
            get_club=mock_get_club,
            get_participation=mock_get_participation,
            get_behavior=mock_get_behavior,
            validate_coach=mock_validate_coach,
        )

@pytest.fixture
def setup_started_match(setup_repositories, monkeypatch):
    s = setup_repositories

    # simulate the creation of a runtime participation
    def fake_create_match_participation(
        db,
        roster,
        mirror_position,
    ):
        return SimpleNamespace(
            formation=roster.formation,
            starters={
                p.player_id
                for p in roster.players
                if p.is_starter
            },
        )

    monkeypatch.setattr(
        league_runner,
        "create_match_participation",
        fake_create_match_participation,
    )

    monkeypatch.setattr(
        league_runner,
        "RuntimeMatch",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    # create a simulated match with two participations
    other_roster = make_roster()
    other_roster.id = 99

    persisted_match = SimpleNamespace(
        id=100,
        match_order=1,
        participations=[
            SimpleNamespace(
                role=MatchRole.LOCAL,
                roster=s.roster,
            ),
            SimpleNamespace(
                role=MatchRole.VISITANTE,
                roster=other_roster,
            ),
        ],
    )

    # build the match with the original roster
    current_match = league_runner.build_round_matches(
        db=s.db,
        matches=[persisted_match],
        duration_seconds=60,
    )[0]

    return s, current_match


# successful update
def test_update_success_changes_configuration_but_not_players(setup_repositories):
    s = setup_repositories

    original_ids = {
        player.player_id
        for player in s.roster.players
    }

    payload = make_payload()
    payload.coach_behavior_id = 7

    update_league_roster(
        s.db,
        LEAGUE_ID,
        USER_ID,
        payload,
    )

    assert s.roster.id == ROSTER_ID
    assert s.roster.formation == Formation.OFFENSIVE
    assert s.roster.coach_behavior_id == 7

    s.validate_coach.assert_called_once_with(
        db=s.db,
        club_id=CLUB_ID,
        coach_behavior_id=7,
    )

    assert {
        player.player_id
        for player in s.roster.players
    } == original_ids

    assert {
        player.player_id
        for player in s.roster.players
        if player.is_starter
    } == {2, 3, 4}

    assert len(s.roster.players) == 6

    s.db.commit.assert_called_once()
    s.db.rollback.assert_not_called()

    s.get_participation.assert_called_once_with(
        db=s.db,
        league_id=LEAGUE_ID,
        club_id=CLUB_ID,
    )


# GET returns correct roster information
def test_get_returns_six_players_and_fields(setup_repositories):
    s = setup_repositories

    response = get_league_roster(
        s.db,
        LEAGUE_ID,
        USER_ID,
    )

    assert response.roster_id == ROSTER_ID
    assert response.formation == Formation.DEFENSIVE
    assert len(response.players) == 6

    assert {
        player.player_id
        for player in response.players
    } == {1, 2, 3, 4, 5, 6}

    assert sum(
        player.is_starter
        for player in response.players
    ) == 3

    assert response.players[0].slot == RosterSlot.LEFT
    assert response.players[0].initial_behavior_id == 1

    assert response.players[3].slot is None
    assert response.players[3].initial_behavior_id is None

    s.db.commit.assert_not_called()


# GET reflects a previous PUT
def test_put_then_get_returns_updated_roster(setup_repositories,):
    s = setup_repositories

    payload = make_payload()
    payload.coach_behavior_id = 7

    update_league_roster(
        s.db,
        LEAGUE_ID,
        USER_ID,
        payload,
    )

    response = get_league_roster(
        s.db,
        LEAGUE_ID,
        USER_ID,
    )

    assert response.formation == Formation.OFFENSIVE
    assert response.coach_behavior_id == 7

    assert {
        player.player_id
        for player in response.players
        if player.is_starter
    } == {2, 3, 4}


# cannot replace the original six players
def test_update_cannot_replace_original_six(setup_repositories):
    s = setup_repositories

    payload = make_payload()
    payload.players[-1].player_id = 99

    with pytest.raises(InvalidRoster, match="same"):
        update_league_roster(
            s.db,
            LEAGUE_ID,
            USER_ID,
            payload,
        )

    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()

    assert {
        player.player_id
        for player in s.roster.players
    } == {1, 2, 3, 4, 5, 6}


# invalid lineup cases
@pytest.mark.parametrize(
    "mutate",
    [
        # only five players
        lambda p: p.players.pop(),

        # duplicate player ID
        lambda p: setattr(p.players[2], "player_id", 2),

        # four starters
        lambda p: setattr(p.players[0], "is_starter", True),

        # substitute with slot
        lambda p: setattr(p.players[0], "slot", "left"),
    ],
)
def test_update_rejects_invalid_roster(
    setup_repositories,
    mutate,
):
    s = setup_repositories

    payload = make_payload()
    mutate(payload)

    with pytest.raises(InvalidRoster):
        update_league_roster(
            s.db,
            LEAGUE_ID,
            USER_ID,
            payload,
        )

    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


# behavior does not exist
def test_update_rejects_nonexistent_behavior(setup_repositories):
    s = setup_repositories

    s.get_behavior.return_value = None

    with pytest.raises(
        InvalidRoster,
        match="Behavior does not exist",
    ):
        update_league_roster(
            s.db,
            LEAGUE_ID,
            USER_ID,
            make_payload(),
        )

    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


# behavior does not belong to user's club
def test_update_rejects_other_club_behavior(setup_repositories):
    s = setup_repositories

    s.get_behavior.return_value = SimpleNamespace(
        id=1,
        is_default=False,
        club_id=999,
    )

    with pytest.raises(
        InvalidRoster,
        match="does not belong",
    ):
        update_league_roster(
            s.db,
            LEAGUE_ID,
            USER_ID,
            make_payload(),
        )

    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


# league does not exist
@pytest.mark.parametrize(
    "operation",
    [update_league_roster, get_league_roster],
)
def test_nonexistent_league_raises_not_found(
    setup_repositories,
    operation,
):
    s = setup_repositories

    s.get_league.return_value = None

    with pytest.raises(LeagueNotFound):
        if operation is update_league_roster:
            operation(
                s.db,
                LEAGUE_ID,
                USER_ID,
                make_payload(),
            )
        else:
            operation(
                s.db,
                LEAGUE_ID,
                USER_ID,
            )


# user does not participate in league
@pytest.mark.parametrize(
    "operation",
    [update_league_roster, get_league_roster],
)
def test_nonparticipant_is_forbidden(
    setup_repositories,
    operation,
):
    s = setup_repositories

    s.get_participation.return_value = None

    with pytest.raises(
        LeagueForbidden,
        match="not participating",
    ):
        if operation is update_league_roster:
            operation(
                s.db,
                LEAGUE_ID,
                USER_ID,
                make_payload(),
            )
        else:
            operation(
                s.db,
                LEAGUE_ID,
                USER_ID,
            )

    s.db.commit.assert_not_called()


# league not started
def test_put_not_started_league_raises_conflict(setup_repositories):
    s = setup_repositories

    s.league.state = LeagueState.POR_COMENZAR

    with pytest.raises(InvalidLeagueState):
        update_league_roster(
            s.db,
            LEAGUE_ID,
            USER_ID,
            make_payload(),
        )

    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()

# mocked db, verified commit is called
def test_update_roster_changes_and_commits(setup_repositories):
    s = setup_repositories

    original_roster_id = s.roster.id
    original_player_ids = {p.player_id for p in s.roster.players}

    update_league_roster(
        db=s.db,
        league_id=LEAGUE_ID,
        user_id=USER_ID,
        data=make_payload(),
    )

    # the same roster is modified
    assert s.roster.id == original_roster_id

    # formation is updated
    assert s.roster.formation == Formation.OFFENSIVE

    # the six original players remain
    assert {p.player_id for p in s.roster.players} == original_player_ids

    # the starting lineup is updated
    assert {
        p.player_id
        for p in s.roster.players
        if p.is_starter
    } == {2, 3, 4}

    # changes are committed
    s.db.commit.assert_called_once()
    s.db.rollback.assert_not_called()



def test_started_match_keeps_original_roster(setup_started_match):
    s, current_match = setup_started_match

    # verify original lineup
    assert current_match.participation_a.starters == {1, 2, 3}
    assert current_match.participation_a.formation == Formation.DEFENSIVE

    # update the league roster
    update_league_roster(
        db=s.db,
        league_id=LEAGUE_ID,
        user_id=USER_ID,
        data=make_payload(),
    )

    # verify the roster has changed
    assert {
        p.player_id
        for p in s.roster.players
        if p.is_starter
    } == {2, 3, 4}

    # verify the already built match remains unchanged
    assert current_match.participation_a.starters == {1, 2, 3}
    assert current_match.participation_a.formation == Formation.DEFENSIVE


def test_update_coach_behavior_invalid(setup_repositories):
    s = setup_repositories

    payload = make_payload()
    payload.coach_behavior_id = 999

    s.validate_coach.side_effect = ValueError(
        "Coach behavior doesn't exist."
    )

    with pytest.raises(
        InvalidRoster,
        match="Coach behavior doesn't exist",
    ):
        update_league_roster(
            db=s.db,
            league_id=LEAGUE_ID,
            user_id=USER_ID,
            data=payload,
        )

    assert s.roster.coach_behavior_id is None
    s.db.commit.assert_not_called()
    s.db.rollback.assert_called_once()


def test_update_remove_coach_behavior(setup_repositories):
    s = setup_repositories

    s.roster.coach_behavior_id = 7

    payload = make_payload()
    payload.coach_behavior_id = None

    update_league_roster(
        db=s.db,
        league_id=LEAGUE_ID,
        user_id=USER_ID,
        data=payload,
    )

    assert s.roster.coach_behavior_id is None

    s.validate_coach.assert_called_once_with(
        db=s.db,
        club_id=CLUB_ID,
        coach_behavior_id=None,
    )

    s.db.commit.assert_called_once()
