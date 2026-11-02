from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.models.match_participation import MatchRole
from app.game.constants import FIELD_CENTER, TICS_PER_SECOND

from app.services import league_runner
from app.services.league_runner import load_round_matches
    

def test_load_round_matches_filters_and_orders():
    db = Mock()

    matches = [Mock(id=10), Mock(id=11)]
    db.scalars.return_value.all.return_value = matches

    result = load_round_matches(
        db=db,
        league_id=5,
        round_number=2,
    )

    assert result == matches

    stmt = db.scalars.call_args.args[0]

    sql = str(
        stmt.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert "matches.league_id = 5" in sql
    assert "matches.round = 2" in sql
    assert "ORDER BY matches.match_order" in sql


def test_load_round_matches_returns_empty_list():
    db = Mock()
    db.scalars.return_value.all.return_value = []

    result = load_round_matches(
        db=db,
        league_id=5,
        round_number=3,
    )

    assert result == []


def test_build_round_matches(monkeypatch):
    db = Mock()

    home_roster = SimpleNamespace(id=10, club_id=1)
    away_roster = SimpleNamespace(id=20, club_id=2)

    home = SimpleNamespace(
        role=MatchRole.LOCAL,
        roster=home_roster,
    )
    away = SimpleNamespace(
        role=MatchRole.VISITANTE,
        roster=away_roster,
    )

    persisted_match = SimpleNamespace(
        id=100,
        participations=[away, home],  # Reversed intentionally
    )

    def build_participation(db, roster, mirror_position):
        return SimpleNamespace(
            club_id=roster.club_id,
            roster_id=roster.id,
        )

    builder = Mock(side_effect=build_participation)

    monkeypatch.setattr(
        league_runner,
        "create_match_participation",
        builder,
    )

    result = league_runner.build_round_matches(
        db=db,
        matches=[persisted_match],
        duration_seconds=90,
    )

    assert len(result) == 1

    match = result[0]

    assert match.match_id == 100
    assert match.participation_a.club_id == 1
    assert match.participation_b.club_id == 2

    assert match.duration_ticks == 90 * TICS_PER_SECOND
    assert match.ball.position == FIELD_CENTER
    assert match.ball.velocity == (0.0, 0.0)

    builder.assert_has_calls([
        call(
            db=db,
            roster=home_roster,
            mirror_position=False,
        ),
        call(
            db=db,
            roster=away_roster,
            mirror_position=True,
        ),
    ])


@pytest.mark.parametrize(
    "roles",
    [
        [MatchRole.LOCAL],
        [MatchRole.LOCAL, MatchRole.LOCAL],
        [MatchRole.VISITANTE, MatchRole.VISITANTE],
    ],
)
def test_build_round_matches_rejects_invalid_participations(roles):
    db = Mock()

    persisted_match = SimpleNamespace(
        id=100,
        participations=[
            SimpleNamespace(role=role)
            for role in roles
        ],
    )

    with pytest.raises(
        ValueError,
        match="must have one home and one away club",
    ):
        league_runner.build_round_matches(
            db=db,
            matches=[persisted_match],
            duration_seconds=90,
        )
