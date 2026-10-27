import pytest
import asyncio

from uuid import UUID, uuid4

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
)

from app.game.default_behaviors import (
    ATTACKER_NAME,
    MIDFIELDER_NAME,
    DEFENDER_NAME,
)
from app.game.preview_match import TEMPORARY_BEHAVIOR_ID




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

    preview_id = create_preview(
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
async def test_create_preview_registers_behaviors(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    code = "def play():\n    return wait()"
    user_id = 1

    with patch(
        "app.services.behavior_preview_service.BehaviorWorkerPool.register_behaviors"
    ) as mock_register:

        preview_id = create_preview(
            db=db,
            user_id=user_id,
            code=code,
            behavior_teammate_1=defaults[0].id,
            behavior_teammate_2=defaults[1].id,
        )

        try:
            mock_register.assert_called_once()

            definitions = mock_register.call_args.args[0]

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


def test_create_preview_cleans_up_on_registration_error(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    with (
        patch(
            "app.services.behavior_preview_service.BehaviorWorkerPool"
        ) as mock_pool_class,
    ):
        mock_pool = mock_pool_class.return_value

        mock_pool.register_behaviors.side_effect = RuntimeError(
            "Registration failed"
        )

        with pytest.raises(RuntimeError, match="Registration failed"):
            create_preview(
                db=db,
                user_id=1,
                code="def play():\n    return wait()",
                behavior_teammate_1=defaults[0].id,
                behavior_teammate_2=defaults[1].id,
            )

        mock_pool.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_stop_preview_by_owner(db):
    defaults = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .all()
    )

    user_id = 1

    preview_id = create_preview(
        db=db,
        user_id=user_id,
        code="def play():\n    return wait()",
        behavior_teammate_1=defaults[0].id,
        behavior_teammate_2=defaults[1].id,
    )

    try:
        owner_id, runner = _active_previews[preview_id]

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

    preview_id = create_preview(
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
    runner.run_preview = AsyncMock()

    worker_pool = MagicMock()

    _active_previews[preview_id] = (1, runner)

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

    worker_pool.shutdown.assert_called_once()
    assert preview_id not in _active_previews


@pytest.mark.asyncio
async def test_run_preview_cleans_up_after_error():
    preview_id = uuid4()

    preview = MagicMock()
    runner = MagicMock()
    runner.run_preview = AsyncMock(
        side_effect=RuntimeError("Simulation failed")
    )

    worker_pool = MagicMock()

    _active_previews[preview_id] = (1, runner)

    with pytest.raises(RuntimeError, match="Simulation failed"):
        await _run_preview(
            preview_id=preview_id,
            preview=preview,
            runner=runner,
            worker_pool=worker_pool,
        )

    worker_pool.shutdown.assert_called_once()
    assert preview_id not in _active_previews
