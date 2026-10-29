import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import engine
from app.models.user import User
from app.models.club import Club
from app.models.roster import Roster, Formation
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.services.league_service import (
    update_standings,
    LeagueParticipationNotFound,
)


@pytest.fixture
def db():
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")

        transaction = connection.get_transaction()

        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

        transaction.rollback()

        with Session(engine) as check_db:
            leagues = check_db.scalar(
                select(func.count())
                .select_from(League)
                .where(League.name == "Standings Test")
            )

            assert leagues == 0, "La liga sigue en la base de datos"


def create_club(db, index: int) -> Club:
    user = User(
        email=f"standings_test_{index}@example.com",
        hash_passwd="test_hash",
    )

    db.add(user)
    db.flush()

    club = Club(
        user_id=user.id,
        name=f"Standings Club {index}",
    )

    db.add(club)
    db.flush()

    return club


def create_league(db, n_clubs: int) -> tuple[League, list[Club]]:
    clubs = [create_club(db, i) for i in range(n_clubs)]

    league = League(
        name="Standings Test",
        match_duration=10,
        max_clubs=8,
        state=LeagueState.INICIADA,
        privacy=LeaguePrivacy.PUBLICA,
        password_hash=None,
        creator_id=clubs[0].id,
    )

    db.add(league)
    db.flush()

    for club in clubs:
        roster = Roster(club_id=club.id, formation=Formation.DEFENSIVE)
        db.add(roster)
        db.flush()

        db.add(
            LeagueParticipation(
                league_id=league.id,
                club_id=club.id,
                roster_id=roster.id,
            )
        )

    db.flush()

    return league, clubs


def get_row(db, league_id: int, club_id: int) -> dict:
    participation = db.get(LeagueParticipation, (league_id, club_id))
    db.refresh(participation)

    return {
        "points": participation.points,
        "played": participation.matches_played,
        "won": participation.matches_won,
        "drawn": participation.matches_drawn,
        "lost": participation.matches_lost,
        "gf": participation.goals_for,
        "ga": participation.goals_against,
    }


def test_local_win(db):
    league, (local, visitante) = create_league(db, 2)

    update_standings(db, league.id, local.id, visitante.id, 3, 1)

    assert get_row(db, league.id, local.id) == {
        "points": 3, "played": 1, "won": 1, "drawn": 0, "lost": 0, "gf": 3, "ga": 1,
    }
    assert get_row(db, league.id, visitante.id) == {
        "points": 0, "played": 1, "won": 0, "drawn": 0, "lost": 1, "gf": 1, "ga": 3,
    }


def test_draw(db):
    league, (local, visitante) = create_league(db, 2)

    update_standings(db, league.id, local.id, visitante.id, 2, 2)

    expected = {"points": 1, "played": 1, "won": 0, "drawn": 1, "lost": 0, "gf": 2, "ga": 2}
    assert get_row(db, league.id, local.id) == expected
    assert get_row(db, league.id, visitante.id) == expected


def test_visitante_win(db):
    league, (local, visitante) = create_league(db, 2)

    update_standings(db, league.id, local.id, visitante.id, 0, 2)

    assert get_row(db, league.id, local.id) == {
        "points": 0, "played": 1, "won": 0, "drawn": 0, "lost": 1, "gf": 0, "ga": 2,
    }
    assert get_row(db, league.id, visitante.id) == {
        "points": 3, "played": 1, "won": 1, "drawn": 0, "lost": 0, "gf": 2, "ga": 0,
    }


def test_results_accumulate(db):
    league, (a, b, c) = create_league(db, 3)

    update_standings(db, league.id, a.id, b.id, 1, 0)
    update_standings(db, league.id, c.id, a.id, 1, 1)

    assert get_row(db, league.id, a.id) == {
        "points": 4, "played": 2, "won": 1, "drawn": 1, "lost": 0, "gf": 2, "ga": 1,
    }


def test_only_the_two_clubs_change(db):
    league, (a, b, c) = create_league(db, 3)

    update_standings(db, league.id, a.id, b.id, 1, 0)

    assert get_row(db, league.id, c.id) == {
        "points": 0, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0,
    }


def test_club_outside_the_league_fails(db):
    league, (local, _) = create_league(db, 2)
    outsider = create_club(db, 99)

    with pytest.raises(LeagueParticipationNotFound):
        update_standings(db, league.id, local.id, outsider.id, 1, 0)


def test_club_against_itself_fails(db):
    league, (local, _) = create_league(db, 2)

    with pytest.raises(ValueError):
        update_standings(db, league.id, local.id, local.id, 1, 0)


def test_negative_goals_fail(db):
    league, (local, visitante) = create_league(db, 2)

    with pytest.raises(ValueError):
        update_standings(db, league.id, local.id, visitante.id, -1, 0)
