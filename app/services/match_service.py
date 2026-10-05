from sqlalchemy.orm import Session
import asyncio
from collections.abc import Awaitable, Callable

from app.game.models.match import Match
from app.game.models.behavior_definition import BehaviorDefinition
from app.repositories import behavior_repository
from app.game.behavior_worker_pool import BehaviorWorkerPool
from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.engine import GameEngine
from app.game.match_runner import MatchRunner

from app.game.active_matches import (
    register_match,
    remove_match,
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
    match_id = register_match(
        match
    )
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

    return match_id