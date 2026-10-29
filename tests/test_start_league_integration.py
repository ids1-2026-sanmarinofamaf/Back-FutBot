from itertools import count

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import engine
from app.models.user import User
from app.models.club import Club
from app.models.roster import Roster, Formation
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.models.match import Match, MatchState
from app.models.match_participation import MatchParticipation, MatchRole
from app.repositories import match_repository
from app.services.fixture_service import generate_fixture
from app.services.league_service import (
    start_league,
    get_league_detail,
    InsufficientLeagueParticipants,
)


SEED = 42


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
                .where(League.name == "Start League Test")
            )

            assert leagues == 0, "La liga sigue en la base de datos"


@pytest.fixture(autouse=True)
def match_ids(monkeypatch):
    # match_id_seq only exists in postgres, tests run on sqlite
    ids = count(1)
    monkeypatch.setattr(
        match_repository,
        "get_next_match_id",
        lambda db: next(ids),
    )


def create_club(db, index: int) -> Club:
    user = User(
        email=f"start_league_test_{index}@example.com",
        hash_passwd="test_hash",
    )

    db.add(user)
    db.flush()

    club = Club(
        user_id=user.id,
        name=f"Start Club {index}",
    )

    db.add(club)
    db.flush()

    return club


def create_league(db, n_clubs: int) -> tuple[League, list[LeagueParticipation], int]:
    clubs = [create_club(db, i) for i in range(n_clubs)]

    league = League(
        name="Start League Test",
        match_duration=10,
        max_clubs=8,
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        password_hash=None,
        creator_id=clubs[0].id,
    )

    db.add(league)
    db.flush()

    participations = []

    for club in clubs:
        # another roster of the club that must not be used in the matches
        other_roster = Roster(club_id=club.id, formation=Formation.OFFENSIVE)
        league_roster = Roster(club_id=club.id, formation=Formation.DEFENSIVE)

        db.add_all([other_roster, league_roster])
        db.flush()

        participation = LeagueParticipation(
            league_id=league.id,
            club_id=club.id,
            roster_id=league_roster.id,
        )

        db.add(participation)
        participations.append(participation)

    # the league already exists before the start, so the rollback of
    # start_league must not undo it (the db fixture discards it at the end)
    db.commit()

    # the user of the creator club starts the league
    return league, participations, clubs[0].user_id


def get_matches(db, league_id: int) -> list[Match]:
    return list(
        db.scalars(
            select(Match)
            .where(Match.league_id == league_id)
            .order_by(Match.match_order)
        ).all()
    )


@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_start_league_creates_one_match_per_pair(db, n):
    league, _, creator_user_id = create_league(db, n)

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    matches = get_matches(db, league.id)

    assert len(matches) == n * (n - 1) // 2
    assert all(match.state == MatchState.POR_COMENZAR for match in matches)

    db.refresh(league)
    assert league.state == LeagueState.INICIADA


def test_every_match_has_one_local_and_one_visitante(db):
    league, _, creator_user_id = create_league(db, 4)

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    for match in get_matches(db, league.id):
        roles = sorted(p.role for p in match.participations)

        assert roles == [MatchRole.LOCAL, MatchRole.VISITANTE]


def test_match_participations_use_the_league_roster(db):
    league, participations, creator_user_id = create_league(db, 4)
    league_roster_by_club = {p.club_id: p.roster_id for p in participations}

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    for match in get_matches(db, league.id):
        for participation in match.participations:
            assert participation.roster_id == league_roster_by_club[participation.club_id]


def test_persisted_fixture_follows_the_seed(db):
    league, participations, creator_user_id = create_league(db, 5)
    club_ids = [p.club_id for p in participations]

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    persisted = []

    for match in get_matches(db, league.id):
        by_role = {p.role: p.club_id for p in match.participations}
        persisted.append((by_role[MatchRole.LOCAL], by_role[MatchRole.VISITANTE]))

    assert persisted == [match for fecha in generate_fixture(club_ids, SEED) for match in fecha]


def test_standings_have_one_row_per_club_in_zero(db):
    league, participations, creator_user_id = create_league(db, 4)

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    detail = get_league_detail(db, league.id)

    assert sorted(row.club_id for row in detail.standings) == sorted(
        p.club_id for p in participations
    )

    for row in detail.standings:
        assert row.points == 0
        assert row.matches_played == 0
        assert row.matches_won == 0
        assert row.matches_drawn == 0
        assert row.matches_lost == 0
        assert row.goals_for == 0
        assert row.goals_against == 0
        assert row.goal_difference == 0


def test_failure_while_creating_matches_leaves_league_untouched(db, monkeypatch):
    league, _, creator_user_id = create_league(db, 4)
    ids = count(1)

    # fails on the third match, after the state and two matches were added
    def failing_next_match_id(db):
        match_id = next(ids)

        if match_id == 3:
            raise RuntimeError("Sequence failure")

        return match_id

    monkeypatch.setattr(
        match_repository,
        "get_next_match_id",
        failing_next_match_id,
    )

    with pytest.raises(RuntimeError):
        start_league(
            db=db,
            league_id=league.id,
            user_id=creator_user_id,
            requested_state=LeagueState.INICIADA,
            seed=SEED,
        )

    db.expire_all()

    assert db.get(League, league.id).state == LeagueState.POR_COMENZAR
    assert get_matches(db, league.id) == []
    assert db.scalar(select(func.count()).select_from(MatchParticipation)) == 0


def test_rejected_start_creates_no_matches(db):
    league, _, creator_user_id = create_league(db, 2)

    with pytest.raises(InsufficientLeagueParticipants):
        start_league(
            db=db,
            league_id=league.id,
            user_id=creator_user_id,
            requested_state=LeagueState.INICIADA,
            seed=SEED,
        )

    db.expire_all()

    assert db.get(League, league.id).state == LeagueState.POR_COMENZAR
    assert get_matches(db, league.id) == []


def test_league_detail_has_no_fixture_before_start(db):
    league, _, _ = create_league(db, 3)

    detail = get_league_detail(db, league.id)

    assert detail.state == LeagueState.POR_COMENZAR
    assert detail.current_participants == 3
    assert detail.fixture is None
    assert detail.standings is None


def test_league_detail_returns_fixture_after_start(db):
    league, _, creator_user_id = create_league(db, 4)

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    detail = get_league_detail(db, league.id)

    assert detail.state == LeagueState.INICIADA
    assert len(detail.fixture) == 6
    assert [item.match_order for item in detail.fixture] == list(range(1, 7))
    # 4 clubs: 3 fechas of 2 matches each
    assert [item.round for item in detail.fixture] == [1, 1, 2, 2, 3, 3]
    assert len(detail.standings) == 4


@pytest.mark.parametrize("n", [3, 4, 5])
def test_persisted_rounds_follow_the_drawn_fechas(db, n):
    league, participations, creator_user_id = create_league(db, n)
    club_ids = [p.club_id for p in participations]

    start_league(
        db=db,
        league_id=league.id,
        user_id=creator_user_id,
        requested_state=LeagueState.INICIADA,
        seed=SEED,
    )

    expected = [
        round_number
        for round_number, fecha in enumerate(generate_fixture(club_ids, SEED), start=1)
        for _ in fecha
    ]
    assert [match.round for match in get_matches(db, league.id)] == expected
