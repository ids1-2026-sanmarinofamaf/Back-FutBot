from sqlalchemy.orm import Session
import asyncio
from collections.abc import Awaitable, Callable

from app.game.models.match import Match, MatchState
from app.game.models.behavior_definition import BehaviorDefinition
from app.repositories import behavior_repository, club_repository
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

_running_match_tasks: set[asyncio.Task] = set()
_worker_pool: BehaviorWorkerPool | None = None


def initialize_worker_pool() -> None:
    """
    Initialize the shared behavior worker pool.

    The pool is created once for the application process.
    """
    global _worker_pool

    if _worker_pool is None:
        _worker_pool = BehaviorWorkerPool(
            size=6,
            timeout_ms=100,
        )


def shutdown_worker_pool() -> None:
    """
    Shut down the shared pool and release its resources.
    """
    global _worker_pool

    if _worker_pool is not None:
        _worker_pool.shutdown()
        _worker_pool = None


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
        worker_pool.release_match(match.match_id)
        remove_match(match.match_id)


def start_match(
    match: Match,
    behaviors: list[BehaviorDefinition],
    on_finished: Callable[[Match], Awaitable[None]] | None = None,
) -> int:
    """
    Register and start a match using the shared worker pool.

    Args:
        match: Match to execute.
        behaviors: Available behavior definitions for the match.
        on_finished: Optional callback executed after the match finishes.

    Returns:
        Identifier of the started match.

    Raises:
        RuntimeError: If the shared worker pool is not initialized.
        ValueError: If the match is already registered.
    """
    worker_pool = _worker_pool

    if worker_pool is None:
        raise RuntimeError("Behavior worker pool is not initialized")

    register_match(match)

    try:
        worker_pool.register_match(
            match.match_id,
            behaviors,
        )

        coordinator = BehaviorCoordinator(
            worker_pool,
            match_id=match.match_id,
        )

        runner = MatchRunner(
            behavior_coordinator=coordinator,
            game_engine=GameEngine(),
        )

        task = asyncio.create_task(
            _run_match(
                match=match,
                runner=runner,
                worker_pool=worker_pool,
                on_finished=on_finished,
            )
        )

    except Exception:
        worker_pool.register_match(match.match_id)
        remove_match(match.match_id)
        raise

    _running_match_tasks.add(task)
    task.add_done_callback(_running_match_tasks.discard)

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

    player.current_behavior_id = behavior_id


async def stop_running_matches() -> None:
    """
    Cancel active match tasks during application shutdown.
    """
    tasks = tuple(_running_match_tasks)

    for task in tasks:
        task.cancel()

    if tasks:
        await asyncio.gather(
            *task,
            return_exceptions=True,
        )
