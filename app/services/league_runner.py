import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timedelta, timezone

from app.models.league import League, LeagueState
from app.models.match import (
    Match as PersistedMatch,
    MatchState as PersistedMatchState,
)
from app.models.match_participation import MatchParticipation, MatchRole
from app.models.roster import Roster

from app.game.models.match import (
    Match as RuntimeMatch,
    MatchState as RuntimeMatchState,
)
from app.game.models.ball import Ball
from app.game.constants import FIELD_CENTER, TICS_PER_SECOND

from app.services.match_builder import create_match_participation
from app.services.match_service import (
    load_match_behaviors,
    start_match_task,
)
from app.services.league_service import update_standings
from app.services.club_statistics_service import update_statistics


def load_round_matches(
    db: Session,
    league_id: int,
    round_number: int,
) -> list[PersistedMatch]:
    """
    Load the matches and current rosters for a league round.
    """
    stmt = (
        select(PersistedMatch)
        .where(
            PersistedMatch.league_id == league_id,
            PersistedMatch.round == round_number,
        )
        .options(
            selectinload(PersistedMatch.participations)
            .selectinload(MatchParticipation.roster)
            .selectinload(Roster.players)
        )
        .order_by(PersistedMatch.match_order)
    )

    return list(
        db.scalars(stmt).all()
    )


def build_round_matches(
    db: Session,
    matches: list[PersistedMatch],
    duration_seconds: int,
) -> list[RuntimeMatch]:
    """
    Build runtime matches using the current rosters of a league round.
    """
    runtime_matches = []

    for match in matches:
        participations = {
            participation.role: participation
            for participation in match.participations
        }

        if (
            len(match.participations) != 2
            or set(participations) != {MatchRole.LOCAL, MatchRole.VISITANTE}
        ):
            raise ValueError(
                f"Match {match.id} must have one home and one away club"
            )

        home = participations[MatchRole.LOCAL]
        away = participations[MatchRole.VISITANTE]

        runtime_match = RuntimeMatch(
            match_id=match.id,
            participation_a=create_match_participation(
                db=db,
                roster=home.roster,
                mirror_position=False,
            ),
            participation_b=create_match_participation(
                db=db,
                roster=away.roster,
                mirror_position=True,
            ),
            ball=Ball(
                position=FIELD_CENTER,
                velocity=(0.0, 0.0),
            ),
            duration_ticks=duration_seconds * TICS_PER_SECOND,
        )

        runtime_matches.append(runtime_match)
    
    return runtime_matches


async def run_round_matches(
    db: Session,
    matches: list[RuntimeMatch]
) -> list[RuntimeMatch]:
    """
    Run all matches in a league round concurrently.
    """
    tasks = []

    try:
        for match in matches:
            behaviors = load_match_behaviors(
                db=db,
                match=match,
            )

            task = start_match_task(
                match=match,
                behaviors=behaviors,
            )

            tasks.append(task)

        await asyncio.gather(*tasks)

    except BaseException:
        #Stop all matches if execution or initialization fails
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        raise

    return matches


def _validate_round_matches(matches: list[RuntimeMatch]) -> None:
    """
    Verify that every match finished with a valid score.
    """

    for match in matches:
        if match.state != RuntimeMatchState.FINISHED:
            raise ValueError(f"Match {match.match_id} has not finished")

        if (
            match.participation_a.goals < 0
            or match.participation_b.goals < 0
        ):
            raise ValueError(f"Invalid score for match {match.match_id}")


def _apply_round_results(
    db: Session,
    league: League,
    persisted_matches: list[PersistedMatch],
    matches_by_id: dict[int, RuntimeMatch],
) -> None:
    """
    Persist match results and update statistics without committing.
    """
    for persisted in persisted_matches:
        runtime = matches_by_id[persisted.id]

        home = runtime.participation_a
        away = runtime.participation_b

        persisted.home_goals = home.goals
        persisted.away_goals = away.goals
        persisted.state = PersistedMatchState.FINALIZADO

        update_standings(
            db=db,
            league_id=league.id,
            local_club_id=home.club_id,
            visitante_club_id=away.club_id,
            local_goals=home.goals,
            visitante_goals=away.goals,
        )

        update_statistics(
            db=db,
            league=league,
            club_a_id=home.club_id,
            club_b_id=away.club_id,
            goals_a=home.goals,
            goals_b=away.goals,
        )


def _get_break_end(
    db: Session,
    league_id: int,
    round_number: int,
) -> datetime | None:
    """
    Return the break deadline if another round exists.
    """
    next_match_id = db.scalar(
        select(PersistedMatch.id)
        .where(
            PersistedMatch.league_id == league_id,
            PersistedMatch.round > round_number,
        )
        .limit(1)
    )

    if next_match_id is None:
        return None

    return datetime.now(timezone.utc) + timedelta(seconds=60)


def complete_round(
    db: Session,
    league_id: int,
    round_number: int,
    matches: list[RuntimeMatch],
) -> None:
    """
    Atomically persist results and statistics for a league round.
    """
    try:
        league = db.scalar(
            select(League)
            .where(League.id == league_id)
            .with_for_update()
        )

        if league is None or league.state != LeagueState.INICIADA:
            raise ValueError("League is not in progress")

        if league.last_completed_round != round_number -1:
            raise ValueError("Invalid round")

        persisted_matches = load_round_matches(
            db,
            league_id,
            round_number,
        )

        matches_by_id = {
            match.match_id: match
            for match in matches
        }

        expected_ids = {
            match.id
            for match in persisted_matches
        }

        if (
            not expected_ids
            or len(matches_by_id) != len(matches)
            or set(matches_by_id) != expected_ids
        ):
            raise ValueError("Round matches do not match the fixture")

        _validate_round_matches(matches)

        _apply_round_results(
            db,
            league,
            persisted_matches,
            matches_by_id,
        )

        league.last_completed_round = round_number
        league.break_ends_at = _get_break_end(
            db,
            league_id,
            round_number,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise
