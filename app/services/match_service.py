from sqlalchemy.orm import Session
import asyncio
from collections.abc import Awaitable, Callable

from app.game.models.match import Match, MatchState
from app.game.models.behavior_definition import BehaviorDefinition
from app.repositories import behavior_repository, club_repository
from app.repositories import coach_behavior_repository
from app.game.behavior_worker_pool import BehaviorWorkerPool
from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.engine import GameEngine
from app.game.match_runner import MatchRunner

from app.game.active_matches import (
    register_match,
    remove_match,
    get_match,
)

# load behaviors in memory for the match
def load_match_behaviors(
    db: Session,
    match: Match,
) -> list[BehaviorDefinition]:

    club_ids = {
        match.participation_a.club_id,
        match.participation_b.club_id,
    }

    behaviors = behavior_repository.get_by_club_ids(
        db=db,
        club_ids=club_ids,
    )

    return [
        BehaviorDefinition(
            id=behavior.id,
            code=behavior.code,
        )
        for behavior in behaviors
    ]

# load in memory the coach (DT) behavior chosen by each club, if any
def load_match_coach_behaviors(
    db: Session,
    match: Match,
) -> list[BehaviorDefinition]:

    coach_behaviors = []

    for participation in (match.participation_a, match.participation_b):
        # the club plays without DT
        if participation.coach_behavior_id is None:
            continue

        # filtering by club ensures the DT belongs to that club
        coach_behavior = coach_behavior_repository.get_by_id_for_club(
            db=db,
            club_id=participation.club_id,
            coach_behavior_id=participation.coach_behavior_id,
        )

        if coach_behavior is None:
            continue

        coach_behaviors.append(
            BehaviorDefinition(
                id=coach_behavior.id,
                code=coach_behavior.code,
            )
        )

    return coach_behaviors

# load in memory, for each club, the behaviors its coach (DT) can assign
def load_match_available_behaviors(
    db: Session,
    match: Match,
) -> None:

    for participation in (match.participation_a, match.participation_b):
        behaviors = behavior_repository.get_available_for_club(
            db=db,
            club_id=participation.club_id,
        )

        # defaults first, so a club behavior with the same name wins
        # (same rule as get_available_by_name)
        behaviors.sort(key=lambda behavior: not behavior.is_default)

        participation.available_behaviors = {
            behavior.name: behavior.id
            for behavior in behaviors
        }

_running_match_tasks: set[asyncio.Task] = set()


async def _run_match(
    match: Match,
    runner: MatchRunner,
    worker_pool: BehaviorWorkerPool,
    on_finished: Callable[[Match], Awaitable[None]] | None = None,
) -> None:

    try:
        await runner.run_match(match)

        if on_finished is not None:
            await on_finished(match)

    finally:
        # delete de worke pool when the match is finished
        worker_pool.shutdown()

        remove_match(
            match.match_id
        )


def start_match(
    match: Match,
    behaviors: list[BehaviorDefinition],
    on_finished: Callable[[Match], Awaitable[None]] | None = None,
    coach_behaviors: list[BehaviorDefinition] | None = None,
) -> int:
    #define the worker pool
    worker_pool = BehaviorWorkerPool(
        size=6,
        timeout_ms=100,
    )
    # register the behaviors in the worker pool
    worker_pool.register_behaviors(
        behaviors
    )
    # register the coach behaviors in a separate registry of the pool,
    # since their ids come from another table
    if coach_behaviors:
        worker_pool.register_coach_behaviors(
            coach_behaviors
        )
    # prepare the coordinator
    coordinator = BehaviorCoordinator(
        worker_pool
    )
    # prepare the engine
    engine = GameEngine()
    # prepare the match runner
    runner = MatchRunner(
        behavior_coordinator=coordinator,
        game_engine=engine,
    )
    # register the match in the active matches
    register_match(match)
    
    # create the background task that executes the match asynchronously
    task = asyncio.create_task(
        _run_match(
            match=match,
            runner=runner,
            worker_pool=worker_pool,
            on_finished=on_finished,
        )
    )
    # keep a reference to the task while the match is running
    _running_match_tasks.add(
        task
    )
    # remove the task from the set automatically when it finishes
    task.add_done_callback(
        _running_match_tasks.discard
    )

    return match.match_id


def change_player_behavior(
    db: Session,
    user_id: int,
    match_id: int,
    player_id: int,
    behavior_id: int,
) -> None:
    match = get_match(match_id)

    if match is None:
        raise LookupError("Match not found")

    if match.state != MatchState.IN_PROGRESS:
        raise ValueError("Match is not in progress")

    club = club_repository.get_by_user_id(db, user_id)

    participation = next(
        (
            p for p in (
                match.participation_a,
                match.participation_b,
            )
            if p.club_id == club.id
        ),
        None,
    )

    if participation is None:
        raise PermissionError("User is not participating in this match")

    player = next(
        (
            p for p in participation.players
            if p.player_id == player_id
        ),
        None,
    )

    if player is None:
        raise LookupError("Player not found in user's team")

    if not player.is_on_field:
        raise ValueError("Player is not on the field")

    behavior = behavior_repository.get_available_by_id(
        db=db,
        club_id=club.id,
        behavior_id=behavior_id,
    )

    if behavior is None:
        raise LookupError("Behavior not available")

    # applied at the beginning of the next tick, over the coach assignments
    participation.plan_behavior_change(player_id, behavior_id)