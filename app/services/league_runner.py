import asyncio
import logging
from functools import partial
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal

from app.game.constants import FIELD_CENTER, TICS_PER_SECOND
from app.game.models.ball import Ball
from app.game.models.match import Match as RuntimeMatch
from app.game.models.match import MatchState as RuntimeMatchState
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.active_league_rounds import (
    register_round,
    remove_round,
)

from app.models.league import League, LeaguePrivacy, LeagueState
from app.models.league_participation import LeagueParticipation
from app.models.match import Match as PersistedMatch
from app.models.match import MatchState as PersistedMatchState
from app.models.match_participation import MatchParticipation, MatchRole
from app.models.roster import Roster

from app.services.club_statistics_service import (
    update_league_statistics,
    update_statistics,
)
from app.services.league_service import (
    update_standings,
    get_league_detail,
)
from app.services.league_websocket_service import league_connection_manager
from app.services import session_websocket_service
from app.services.match_builder import create_match_participation
from app.services.match_service import load_match_behaviors, start_match_task

from app.schemas.league_websocket import (
    LeagueRoundStartedEvent,
    LeagueRoundFinishedEvent,
    LeagueFinishedEvent,
    LeagueMatchResult,
)


ROUND_BREAK_SECONDS = 60


logger = logging.getLogger(__name__)


_running_leagues: dict[int, asyncio.Task[None]] = {}


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
    matches: list[RuntimeMatch],
    behaviors_by_match: dict[int, list[BehaviorDefinition]],
    started_event: LeagueRoundStartedEvent | None = None,
) -> list[RuntimeMatch]:
    """
    Run all matches of a round concurrently.
    """
    tasks = []

    try:
        for match in matches:
            task = start_match_task(
                match=match,
                behaviors=behaviors_by_match[match.match_id],
            )
            tasks.append(task)

        if started_event is not None:
            await _notify_league_event(
                started_event.league_id,
                started_event,
            )

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


def _finish_league(db: Session, league: League) -> None:
    """Finalize the league and update global statistics if public."""

    participants = list(
        db.scalars(
            select(LeagueParticipation)
            .where(LeagueParticipation.league_id == league.id)
        ).all()
    )

    winner = max(
        participants,
        key=lambda p: (
            p.points,
            p.goals_for - p.goals_against,
            p.goals_for,
            -p.club_id,
        ),
    )

    if league.privacy == LeaguePrivacy.PUBLICA:
        update_league_statistics(
            db=db,
            club_ids=[p.club_id for p in participants],
            winner_id=winner.club_id,
        )

    league.state = LeagueState.FINALIZADA
    league.break_ends_at = None


def complete_round(
    db: Session,
    league_id: int,
    round_number: int,
    matches: list[RuntimeMatch],
    is_last_round: bool,
) -> None:
    """
    Commit one full round, including finalization if it is the last.
    """
    try:
        league = db.scalar(
            select(League).where(League.id == league_id).with_for_update()
        )

        if league is None or league.state != LeagueState.INICIADA:
            raise ValueError("League is not in progress")
        
        if league.last_completed_round != round_number - 1:
            raise ValueError("Invalid round")

        persisted_matches = load_round_matches(db, league_id, round_number)
        matches_by_id = {match.match_id: match for match in matches}
        expected_ids = {match.id for match in persisted_matches}

        if (
            not expected_ids
            or len(matches_by_id) != len(matches)
            or set(matches_by_id) != expected_ids
        ):
            raise ValueError("Round matches do not match the fixture")

        _validate_round_matches(matches)

        _apply_round_results(db, league, persisted_matches, matches_by_id)

        league.last_completed_round = round_number

        if is_last_round:
            _finish_league(db, league)

        else:
            league.break_ends_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=ROUND_BREAK_SECONDS)
            )

        db.commit()

    except Exception:
        db.rollback()
        raise


async def run_league(league_id: int) -> None:
    """
    Execute the league round by round, resuming from saved progress.
    """
    while True:
        # 1. Determine the next round and whether a break is still pending.
        with SessionLocal() as db:
            league = db.get(League, league_id)

            if league is None:
                raise ValueError("League does not exist")
            
            if league.state == LeagueState.FINALIZADA:
                return
            
            if league.state != LeagueState.INICIADA:
                raise ValueError("League is not in progress")

            round_number = league.last_completed_round + 1
            duration_seconds = league.match_duration
            break_ends_at = league.break_ends_at

            last_round = db.scalar(
                select(func.max(PersistedMatch.round))
                .where(PersistedMatch.league_id == league_id)
            )

            if last_round is None or round_number > last_round:
                raise ValueError("Invalid league fixture or progress")

        # 2. Wait outside of any database session.
        if break_ends_at is not None:
            if break_ends_at.tzinfo is None:
                break_ends_at = break_ends_at.replace(tzinfo=timezone.utc)

            seconds = (break_ends_at - datetime.now(timezone.utc)).total_seconds()
            await asyncio.sleep(max(0, seconds))

        # 3. Load the latest rosters immediately before starting the round.
        with SessionLocal() as db:
            persisted = load_round_matches(
                db,
                league_id,
                round_number
            )

            if not persisted:
                raise ValueError(f"No matches in round {round_number}")
            
            matches = build_round_matches(
                db,
                persisted,
                duration_seconds
            )

            behaviors = {
                match.match_id: load_match_behaviors(db=db, match=match)
                for match in matches
            }

        register_round(league_id, round_number)

        try:
            # 4. Run matches with no open DB session.
            await run_round_matches(
                matches=matches,
                behaviors_by_match=behaviors,
                started_event=LeagueRoundStartedEvent(
                    league_id=league_id,
                    round=round_number,
                    match_ids=[match.match_id for match in matches]
                )
            )

            # 5. Confirm the entire round in a single transaction.
            with SessionLocal() as db:
                complete_round(
                    db=db,
                    league_id=league_id,
                    round_number=round_number,
                    matches=matches,
                    is_last_round=(round_number == last_round),
                )

                detail = get_league_detail(db, league_id)

                finish_round_event = LeagueRoundFinishedEvent(
                    league_id=league_id,
                    round=round_number,
                    results= [
                        LeagueMatchResult(
                            match_id=match.match_id,
                            score=match.score,
                        )
                        for match in detail.fixture
                        if match.round == round_number
                    ],
                    standings=detail.standings,
                    break_ends_at=detail.break_ends_at,   
                )

        finally:
            remove_round(league_id)

        await _notify_league_event(
            league_id,
            finish_round_event,
        )

        if detail.state == LeagueState.FINALIZADA:
            finish_league_event = LeagueFinishedEvent(
                league_id=league_id,
            )

            await _notify_league_event(
                league_id,
                finish_league_event,
            )

            await session_websocket_service.notify_leagues_updated()

            return


def _on_league_finished(
    league_id: int,
    task: asyncio.Task[None],
) -> None:
    _running_leagues.pop(league_id, None)

    if task.cancelled():
        return

    try:
        task.result()

    except Exception:
        logger.exception("League %s execution failed", league_id)


def start_league_runner(league_id: int) -> None:
    if league_id in _running_leagues:
        return

    task = asyncio.create_task(run_league(league_id))

    _running_leagues[league_id] = task

    task.add_done_callback(
        partial(_on_league_finished, league_id)
    )


async def stop_league_runners() -> None:
    tasks = list(_running_leagues.values())

    for task in tasks:
        task.cancel()

    if tasks:
        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )


async def _notify_league_event(
    league_id: int,
    event: (
        LeagueRoundStartedEvent
        | LeagueRoundFinishedEvent
        | LeagueFinishedEvent
    ),
) -> None:
    try:
        await league_connection_manager.broadcast(
            league_id,
            event
        )

    except Exception:
        logger.exception(
            "Failed to notify league %s about event  %s",
            league_id,
            event.type,
        )
