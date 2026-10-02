from dataclasses import replace

import pytest

from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.models.actions import MoveAction, WaitAction


class FakeWorkerPool:
    """
    Test double for BehaviorWorkerPool.

    It stores the jobs received from the coordinator and returns a predefined
    mapping of player actions without creating worker processes.
    """

    def __init__(self, actions):
        self.actions = actions
        self.received_jobs = []

    def execute(self, jobs):
        self.received_jobs = jobs
        return self.actions


def test_coordinator_returns_action_for_each_on_field_player(
    match_snapshot,
):
    pool = FakeWorkerPool(
        {
            1: MoveAction((1.0, 0.0), 1.0),
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    actions = coordinator.get_actions(match_snapshot)

    assert set(actions.keys()) == {1, 2, 3, 7, 8, 9}


def test_coordinator_creates_jobs_for_on_field_players(
    match_snapshot,
):
    pool = FakeWorkerPool(
        {
            1: WaitAction(),
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    coordinator.get_actions(match_snapshot)

    job_player_ids = {
        job.player_id
        for job in pool.received_jobs
    }

    assert job_player_ids == {1, 2, 3, 7, 8, 9}

    for job in pool.received_jobs:
        assert job.behavior_id is not None
        assert job.context.player[0] == job.player_id


def test_coordinator_does_not_create_jobs_for_substitutes(
    match_snapshot,
):
    pool = FakeWorkerPool(
        {
            1: WaitAction(),
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    coordinator.get_actions(match_snapshot)

    job_player_ids = {
        job.player_id
        for job in pool.received_jobs
    }

    assert 4 not in job_player_ids
    assert 5 not in job_player_ids
    assert 6 not in job_player_ids

    assert 10 not in job_player_ids
    assert 11 not in job_player_ids
    assert 12 not in job_player_ids


def test_coordinator_assigns_wait_without_job_for_forced_wait(
    player_a_snapshot,
    match_snapshot,
):
    forced_wait_player = replace(
        player_a_snapshot,
        forced_wait_remaining=5,
    )

    modified_match = replace(
        match_snapshot,
        players_a=(
            forced_wait_player,
            *match_snapshot.players_a[1:],
        ),
    )

    pool = FakeWorkerPool(
        {
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    actions = coordinator.get_actions(modified_match)

    assert isinstance(actions[1], WaitAction)

    assert all(
        job.player_id != 1
        for job in pool.received_jobs
    )


def test_coordinator_assigns_wait_without_job_if_behavior_is_missing(
    player_a_snapshot,
    match_snapshot,
):
    player_without_behavior = replace(
        player_a_snapshot,
        current_behavior_id=None,
    )

    modified_match = replace(
        match_snapshot,
        players_a=(
            player_without_behavior,
            *match_snapshot.players_a[1:],
        ),
    )

    pool = FakeWorkerPool(
        {
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    actions = coordinator.get_actions(modified_match)

    assert isinstance(actions[1], WaitAction)

    assert all(
        job.player_id != 1
        for job in pool.received_jobs
    )


def test_coordinator_raises_if_action_is_missing(
    match_snapshot,
):
    pool = FakeWorkerPool(
        {
            1: WaitAction(),
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            # Player 9 missing
        }
    )

    coordinator = BehaviorCoordinator(pool)

    with pytest.raises(RuntimeError):
        coordinator.get_actions(match_snapshot)


def test_coordinator_raises_if_action_exists_for_off_field_player(
    match_snapshot,
):
    pool = FakeWorkerPool(
        {
            1: WaitAction(),
            2: WaitAction(),
            3: WaitAction(),
            7: WaitAction(),
            8: WaitAction(),
            9: WaitAction(),

            # Substitute / unexpected player
            10: WaitAction(),
        }
    )

    coordinator = BehaviorCoordinator(pool)

    with pytest.raises(RuntimeError):
        coordinator.get_actions(match_snapshot)