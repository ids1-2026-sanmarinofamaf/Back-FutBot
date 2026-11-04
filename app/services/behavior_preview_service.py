import asyncio
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.repositories import behavior_repository
from app.repositories import match_repository

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

from app.services.match_service import get_worker_pool
from app.services.behavior_preview_websocket_service import (
    preview_connection_manager,
)
from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage


PREVIEW_START_DELAY = 5

_active_previews: dict[UUID, tuple[int, PreviewRunner]] = {}
_running_preview_tasks: set[asyncio.Task] = set()
_pending_preview_users: set[int] = set()


async def _run_preview(
    preview_id: UUID,
    preview: Match,
    runner: PreviewRunner,
    worker_pool: BehaviorWorkerPool,
) -> None:
    try:
        try:
            await asyncio.wait_for(
                runner.stop_event.wait(),
                timeout=PREVIEW_START_DELAY,
            )
        except asyncio.TimeoutError:
            pass

        if runner.stop_event.is_set():
            await preview_connection_manager.broadcast(
                preview_id,
                BehaviorPreviewFinishedMessage(
                    reason="stopped",
                )
            )
            await preview_connection_manager.close_preview_connection(
                preview_id,
            )
            return

        await runner.run_preview(preview_id, preview)

    except Exception:
        await preview_connection_manager.close_preview_connection(
            preview_id,
        )
        raise

    finally:
        try: 
            await asyncio.to_thread(
                worker_pool.release_match,
                preview.match_id,
            )

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


async def create_preview(
    db: Session,
    user_id: int,
    code: str,
    behavior_teammate_1: int,
    behavior_teammate_2: int,
) -> UUID:
    if (
        user_id in _pending_preview_users
        or any(
            owner_id == user_id
            for owner_id, _ in _active_previews.values()
        )
    ):
        raise ValueError("User already has an active preview")



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

    match_id = match_repository.get_next_match_id(db)

    preview = create_preview_match(
        match_id,
        behavior_teammate_1,
        behavior_teammate_2,
        default_ids,
    )

    worker_pool = get_worker_pool()
    _pending_preview_users.add(user_id)

    try:
        await asyncio.to_thread(
            worker_pool.register_match,
            preview.match_id,
            definitions,
        )

        runner = PreviewRunner(
            behavior_coordinator=BehaviorCoordinator(
                worker_pool,
                match_id=preview.match_id,
            ),
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
        await asyncio.to_thread(
            worker_pool.release_match,
            preview.match_id,
        )
        raise

    finally:
        _pending_preview_users.discard(user_id)

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


async def stop_running_previews() -> None:
    tasks = tuple(_running_preview_tasks)
    previews = tuple(_active_previews.values())

    for owner_id, runner in previews:
        runner.stop()

    if tasks:
        await asyncio.gather(
            *tasks,
            return_exceptions=True
        )