import asyncio
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories import behavior_repository

from app.game.preview_match import (
    create_preview_match,
    TEMPORARY_BEHAVIOR_ID,
)
from app.game.preview_runner import PreviewRunner
from app.game.behavior_worker_pool import BehaviorWorkerPool
from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.engine import GameEngine

from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.match import Match


_active_previews: dict[UUID, tuple[int, PreviewRunner]] = {}
_running_preview_tasks: set[asyncio.Task] = set()


async def _run_preview(
    preview_id: UUID,
    preview: Match,
    runner: PreviewRunner,
    worker_pool: BehaviorWorkerPool,
) -> None:
    try:
        await runner.run_preview(preview_id, preview)
    finally:
        try: 
            worker_pool.shutdown()
        finally:
            _active_previews.pop(preview_id, None)


def load_preview_behaviors(
    db: Session,
    behavior_teammate_1: int,
    behavior_teammate_2: int,
) -> tuple[list[BehaviorDefinition], dict[str, int]]:
    """
    Load the default behaviors required for a preview.

    Returns the definitions to register in the worker pool
    and a mapping of default behavior names to IDs.
    """
    defaults = behavior_repository.get_default_behaviors(db)

    defaults_by_id = {
        behavior.id: behavior
        for behavior in defaults
    }

    if (
        behavior_teammate_1 not in defaults_by_id
        or behavior_teammate_2 not in defaults_by_id
    ):
        raise ValueError("Invalid default behavior")

    definitions = [
        BehaviorDefinition(id=behavior.id, code=behavior.code)
        for behavior in defaults
    ]

    default_ids = {
        behavior.name: behavior.id
        for behavior in defaults
    }

    return definitions, default_ids


def create_preview(
    db: Session,
    user_id: int,
    code: str,
    behavior_teammate_1: int,
    behavior_teammate_2: int,
) -> UUID:
    definitions, default_ids = load_preview_behaviors(
        db,
        behavior_teammate_1,
        behavior_teammate_2,
    )

    definitions.append(
        BehaviorDefinition(
            id=TEMPORARY_BEHAVIOR_ID,
            code=code,
        )
    )

    preview = create_preview_match(
        behavior_teammate_1,
        behavior_teammate_2,
        default_ids,
    )

    worker_pool = BehaviorWorkerPool(
        size=6,
        timeout_ms=100,
    )

    try:
        worker_pool.register_behaviors(definitions)

        runner = PreviewRunner(
            behavior_coordinator=BehaviorCoordinator(worker_pool),
            game_engine=GameEngine(),
        )

        preview_id = uuid4()

        task = asyncio.create_task(
            _run_preview(
                preview_id,
                preview,
                runner,
                worker_pool,
            )
        )

        _active_previews[preview_id] = (user_id, runner)

        _running_preview_tasks.add(task)
        task.add_done_callback(_running_preview_tasks.discard)

    except Exception:
        worker_pool.shutdown()
        raise

    return preview_id


def stop_preview(
    preview_id: UUID,
    user_id: int,
) -> None:
    session = _active_previews.get(preview_id)

    if session is None:
        raise LookupError("Preview not found")

    owner_id, runner = session

    if owner_id != user_id:
        raise LookupError("Preview not found")

    runner.stop()


def preview_belongs_to_user(
    preview_id: UUID,
    user_id: int,
) -> bool:
    session = _active_previews.get(preview_id)

    return session is not None and session[0] == user_id