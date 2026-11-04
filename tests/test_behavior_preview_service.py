import pytest
import asyncio

from uuid import UUID, uuid4
from itertools import count
from functools import partial

from unittest.mock import patch, AsyncMock, MagicMock

from app.database import SessionLocal
from app.core.security import get_password_hash

from app.models.behavior import Behavior
from app.models.club import Club
from app.models.user import User
from app.services.behavior_preview_service import (
    load_preview_behaviors,
    create_preview,
    stop_preview,
    _active_previews,
    _running_preview_tasks,
    _run_preview,
    stop_running_previews,
)

from app.game.default_behaviors import (
    ATTACKER_NAME,
    MIDFIELDER_NAME,
    DEFENDER_NAME,
)
from app.game.preview_match import TEMPORARY_BEHAVIOR_ID
from app.game.behavior_worker_pool import BehaviorWorkerPool




@pytest.fixture(autouse=True)
def shared_pool():
    pool = MagicMock(spec=BehaviorWorkerPool)

    with (
        patch(
            "app.services.behavior_preview_service.get_worker_pool",
            return_value=pool,
        ),
        patch(
            "app.services.behavior_preview_service.match_repository.get_next_match_id",
            side_effect=count(1),
        ),
    ):
        yield pool


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def test_load_preview_behaviors_returns_defaults(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    assert len(defaults) == 3

    teammate_1 = defaults[0]
    teammate_2 = defaults[1]

    definitions, default_ids = load_preview_behaviors(
        db=db,
        behavior_teammate_1=teammate_1.id,
        behavior_teammate_2=teammate_2.id,
    )

    assert {definition.id for definition in definitions} == {
        behavior.id for behavior in defaults
    }

    assert default_ids == {
        ATTACKER_NAME: next(
            b.id for b in defaults if b.name == ATTACKER_NAME
        ),
        MIDFIELDER_NAME: next(
            b.id for b in defaults if b.name == MIDFIELDER_NAME
        ),
        DEFENDER_NAME: next(
            b.id for b in defaults if b.name == DEFENDER_NAME
        ),
    }

    assert {
        definition.id: definition.code
        for definition in definitions
    } == {
        behavior.id: behavior.code
        for behavior in defaults
    }


def test_load_preview_behaviors_rejects_custom_behavior(db):
    user = User(
        email="preview-test@mail.com",
        hash_passwd=get_password_hash("testpassword"),
        club=Club(name="Preview Test Club"),
    )

    db.add(user)
    db.commit()

    custom = Behavior(
        club_id=user.club.id,
        name="Custom behavior",
        code="def play():\n    return wait()",
        is_default=False,
    )

    db.add(custom)
    db.commit()

    default = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .first()
    )

    try:
        with pytest.raises(ValueError, match="Invalid default behavior"):
            load_preview_behaviors(
                db=db,
                behavior_teammate_1=default.id,
                behavior_teammate_2=custom.id,
            )
    finally:
        db.delete(custom)
        db.delete(user)
        db.commit()


def test_load_preview_behaviors_rejects_nonexistent_behavior(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    default_id = defaults[0].id

    nonexistent_id = (
        db.query(Behavior.id)
        .order_by(Behavior.id.desc())
        .first()[0] + 1
    )

    with pytest.raises(ValueError, match="Invalid default behavior"):
        load_preview_behaviors(
            db=db,
            behavior_teammate_1=default_id,
            behavior_teammate_2=nonexistent_id,
        )


@pytest.mark.asyncio
async def test_create_preview_success(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    user_id = 1
    code = "def play():\n    return wait()"

    preview_id = await create_preview(
        db=db,
        user_id=user_id,
        code=code,
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    try:
        assert isinstance(preview_id, UUID)
        assert preview_id in _active_previews

        owner_id, runner = _active_previews[preview_id]

        assert owner_id == user_id
        assert runner is not None

    finally:
        stop_preview(preview_id, user_id)
        await asyncio.gather(*tuple(_running_preview_tasks))


@pytest.mark.asyncio
async def test_create_preview_rejects_second_active_preview(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    user_id = 1

    preview_id = await create_preview(
        db=db,
        user_id=user_id,
        code="def play():\n    return wait()",
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    try:
        with patch(
            "app.services.behavior_preview_service.get_worker_pool"
        ) as mock_get_pool:

            with pytest.raises(
                ValueError,
                match="User already has an active preview",
            ):
                await create_preview(
                    db=db,
                    user_id=user_id,
                    code="def play():\n    return wait()",
                    behavior_teammate_1=defaults[0].id,
                    behavior_teammate_2=defaults[1].id,
                )

            mock_get_pool.assert_not_called()

        assert preview_id in _active_previews

    finally:
        stop_preview(preview_id, user_id)
        await asyncio.gather(*tuple(_running_preview_tasks))

    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_create_preview_registers_behaviors(db, shared_pool):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    code = "def play():\n    return wait()"
    user_id = 1

    preview_id = await create_preview(
        db=db,
        user_id=user_id,
        code=code,
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    try:
        shared_pool.register_match.assert_called_once()
        match_id, definitions = shared_pool.register_match.call_args.args

        assert isinstance(match_id, int)
        assert match_id > 0

        registered_behaviors = {
            behavior.id: behavior.code
            for behavior in definitions
        }

        assert len(registered_behaviors) == 4

        for behavior in defaults:
            assert registered_behaviors[behavior.id] == behavior.code

        assert registered_behaviors[TEMPORARY_BEHAVIOR_ID] == code

    finally:
        stop_preview(preview_id, user_id)
        await asyncio.gather(*tuple(_running_preview_tasks))

    shared_pool.release_match.assert_called_once_with(match_id)
    shared_pool.shutdown.assert_not_called()


@pytest.mark.asyncio
async def test_create_preview_cleans_up_on_registration_error(db, shared_pool):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    shared_pool.register_match.side_effect = RuntimeError(
        "Registration failed"
    )

    with pytest.raises(RuntimeError, match="Registration failed"):
        await create_preview(
            db=db,
            user_id=1,
            code="def play():\n    return wait()",
            behavior_teammate_1=defaults[0].id,
            behavior_teammate_2=defaults[1].id,
        )

    match_id = shared_pool.register_match.call_args.args[0]

    shared_pool.release_match.assert_called_once_with(match_id)
    shared_pool.shutdown.assert_not_called()


@pytest.mark.asyncio
async def test_stop_preview_by_owner(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    user_id = 1

    preview_id = await create_preview(
        db=db,
        user_id=user_id,
        code="def play():\n    return wait()",
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    owner_id, runner = _active_previews[preview_id]

    try:
        assert owner_id == user_id

        stop_preview(preview_id, user_id)

        assert runner.stop_event.is_set()

    finally:
        runner.stop()
        await asyncio.gather(*tuple(_running_preview_tasks))

    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_stop_preview_by_another_user(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    owner_id = 1
    other_user_id = 2

    preview_id = await create_preview(
        db=db,
        user_id=owner_id,
        code="def play():\n    return wait()",
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    try:
        with pytest.raises(LookupError, match="Preview not found"):
            stop_preview(preview_id, other_user_id)

        assert preview_id in _active_previews

        _, runner = _active_previews[preview_id]

        assert not runner.stop_event.is_set()

    finally:
        stop_preview(preview_id, owner_id)
        await asyncio.gather(*tuple(_running_preview_tasks))

    assert preview_id not in _active_previews


def test_stop_preview_not_found():
    nonexistent_id = uuid4()

    with pytest.raises(LookupError, match="Preview not found"):
        stop_preview(
            preview_id=nonexistent_id,
            user_id=1,
        )


@pytest.mark.asyncio
async def test_run_preview_cleans_up_after_completion():
    preview_id = uuid4()

    preview = MagicMock()

    runner = MagicMock()
    runner.stop_event = asyncio.Event()
    runner.run_preview = AsyncMock()

    worker_pool = MagicMock()

    _active_previews[preview_id] = (1, runner)

    with patch(
        "app.services.behavior_preview_service.PREVIEW_START_DELAY",
        0.001,
    ):
        await _run_preview(
            preview_id=preview_id,
            preview=preview,
            runner=runner,
            worker_pool=worker_pool,
        )

    runner.run_preview.assert_awaited_once_with(
        preview_id,
        preview,
    )

    worker_pool.release_match.assert_called_once_with(preview.match_id)
    worker_pool.shutdown.assert_not_called()
    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_run_preview_cleans_up_after_error():
    preview_id = uuid4()

    preview = MagicMock()

    runner = MagicMock()
    runner.stop_event = asyncio.Event()
    runner.run_preview = AsyncMock(
        side_effect=RuntimeError("Simulation failed")
    )

    worker_pool = MagicMock()

    _active_previews[preview_id] = (1, runner)

    with (
        patch(
            "app.services.behavior_preview_service.PREVIEW_START_DELAY",
            0.001,
        ),
        patch(
            "app.services.behavior_preview_service."
            "preview_connection_manager.close_preview_connection",
            new_callable=AsyncMock,
        ) as mock_close,
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulation failed",
        ):
            await _run_preview(
                preview_id=preview_id,
                preview=preview,
                runner=runner,
                worker_pool=worker_pool,
            )

    runner.run_preview.assert_awaited_once_with(
        preview_id,
        preview,
    )

    mock_close.assert_awaited_once_with(preview_id)

    worker_pool.release_match.assert_called_once_with(preview.match_id)
    worker_pool.shutdown.assert_not_called()
    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_run_preview_stopped_before_start():
    preview_id = uuid4()

    preview = MagicMock()

    runner = MagicMock()
    runner.stop_event = asyncio.Event()
    runner.run_preview = AsyncMock()

    worker_pool = MagicMock()

    _active_previews[preview_id] = (1, runner)

    with (
        patch(
            "app.services.behavior_preview_service."
            "preview_connection_manager.broadcast",
            new_callable=AsyncMock,
        ) as mock_broadcast,
        patch(
            "app.services.behavior_preview_service."
            "preview_connection_manager.close_preview_connection",
            new_callable=AsyncMock,
        ) as mock_close,
    ):
        task = asyncio.create_task(
            _run_preview(
                preview_id=preview_id,
                preview=preview,
                runner=runner,
                worker_pool=worker_pool,
            )
        )

        await asyncio.sleep(0)

        runner.stop_event.set()

        await task

    runner.run_preview.assert_not_awaited()

    mock_broadcast.assert_awaited_once()

    message = mock_broadcast.await_args.args[1]

    assert message.event == "preview_finished"
    assert message.reason == "stopped"

    mock_close.assert_awaited_once_with(preview_id)

    worker_pool.release_match.assert_called_once_with(preview.match_id)
    worker_pool.shutdown.assert_not_called()
    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_shutdown_stops_previews_and_releases_shared_pool_resources(
    db,
    shared_pool,
):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    previews = []

    try:
        for user_id in (1, 2):
            preview_id = await create_preview(
                db=db,
                user_id=user_id,
                code="def play():\n    return wait()",
                behavior_teammate_1=defaults[0].id,
                behavior_teammate_2=defaults[1].id,
            )
            previews.append(preview_id)

        runners = [
            _active_previews[preview_id][1]
            for preview_id in previews
        ]
        tasks = tuple(_running_preview_tasks)
        registered_ids = {
            registration.args[0]
            for registration in shared_pool.register_match.call_args_list
        }

        await asyncio.wait_for(stop_running_previews(), timeout=1)

        assert all(runner.stop_event.is_set() for runner in runners)
        assert all(task.done() for task in tasks)
        assert all(
            preview_id not in _active_previews
            for preview_id in previews
        )

        released_ids = {
            release.args[0]
            for release in shared_pool.release_match.call_args_list
        }

        assert len(registered_ids) == 2
        assert shared_pool.release_match.call_count == 2
        assert released_ids == registered_ids
        shared_pool.shutdown.assert_not_called()

    finally:
        await stop_running_previews()


async def pause_registration(
    function,
    *args,
    register_match,
    started,
    proceed,
):
    if function == register_match:
        started.set()
        await proceed.wait()

    return function(*args)


@pytest.mark.asyncio
async def test_create_preview_rejects_user_with_pending_registration(
    db,
    shared_pool,
):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    started = asyncio.Event()
    proceed = asyncio.Event()

    data = {
        "db": db,
        "user_id": 1,
        "code": "def play():\n    return wait()",
        "behavior_teammate_1": defaults[0].id,
        "behavior_teammate_2": defaults[1].id,
    }

    with patch(
        "app.services.behavior_preview_service.asyncio.to_thread",
        new=partial(
            pause_registration,
            register_match=shared_pool.register_match,
            started=started,
            proceed=proceed,
        ),
    ):
        first_request = asyncio.create_task(create_preview(**data))

        try:
            await asyncio.wait_for(started.wait(), timeout=1)

            assert not first_request.done()
            assert not _active_previews

            with pytest.raises(
                ValueError,
                match="User already has an active preview",
            ):
                await asyncio.wait_for(
                    create_preview(**data),
                    timeout=1,
                )

            proceed.set()
            preview_id = await asyncio.wait_for(
                first_request,
                timeout=1,
            )

            assert preview_id in _active_previews
            shared_pool.register_match.assert_called_once()

        finally:
            proceed.set()

            try:
                await asyncio.wait_for(first_request, timeout=1)
            finally:
                await stop_running_previews()
