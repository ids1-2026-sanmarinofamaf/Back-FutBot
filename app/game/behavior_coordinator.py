from app.game.behavior_worker_pool import BehaviorWorkerPool
from app.game.context_builder import build_behavior_context, build_coach_context

from app.game.models.match import Match, MatchSnapshot
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.models.behavior_job import BehaviorJob
from app.game.models.coach_job import CoachJob
from app.game.types import Assignment, CoachTrigger


Action = MoveAction | KickAction | WaitAction

class BehaviorCoordinator:
    """
    Coordinate behavior execution for the players currently on the field.

    The coordinator translates a match snapshot into behavior execution jobs,
    delegates those jobs to the worker pool, and returns one action per player.
    """
    def __init__(
        self,
        worker_pool: BehaviorWorkerPool,
        match_id: int,
    ) -> None:
        """
        Initialize the coordinator fot a specific match.

        Args:
            worker_pool: Shared pool used to execute behaviors.
            match_id: Identifier of the match.
        """
        self._worker_pool = worker_pool
        self._match_id = match_id


    def get_actions(
        self,
        match_snapshot: MatchSnapshot,
    ) -> dict[int, Action]:
        """
        Return one action for each player currently on the field.

        Players under a forced wait penalty or without an assigned behavior receive
        WaitAction directly. All remaining players are converted into BehaviorJob
        instances and executed through the worker pool.

        Args:
            match_snapshot: Immutable snapshot of the current match state.

        Returns:
            A mapping from each on-field player identifier to the action selected
            for the current tic.

        Raises:
            RuntimeError: If the resulting actions do not match the on-field players.
        """
        actions: dict[int, Action] = {}
        jobs: list[BehaviorJob] = []

        for player in match_snapshot.players_a + match_snapshot.players_b:
            if not player.is_on_field:  #ignore substitute
                continue

            if (
                player.forced_wait_remaining > 0    #Not behavior or penalized
                or player.current_behavior_id is None
            ):
                actions[player.player_id] = WaitAction()
                continue                                    

            context = build_behavior_context(
                match_snapshot,
                player,
            )

            jobs.append(
                BehaviorJob(
                    player_id=player.player_id,
                    behavior_id=player.current_behavior_id,
                    context=context,
                )
            )

        worker_actions = self._worker_pool.execute(
            jobs,
            match_id=self._match_id,
        )
        actions.update(worker_actions)

        # Check all players in field have an action for next tic
        on_field_player_ids = {
            player.player_id
            for player in match_snapshot.players_a + match_snapshot.players_b
            if player.is_on_field
        }

        if set(actions.keys()) != on_field_player_ids:
            raise RuntimeError(
                "Missing or unexpected actions for on-field players"
            )

        return actions



        


    def get_coach_assignments(
        self,
        match: Match,
        triggers: list[tuple[int, CoachTrigger]],
    ) -> dict[int, list[Assignment]]:
        """
        Execute the coach of each triggered club and return its assignments.

        Clubs without a coach behavior are skipped. If the same club is
        triggered more than once in the tic, its coach runs once per trigger
        and the assignments are concatenated in trigger order.

        Args:
            match: Current match state.
            triggers: Coach triggers generated during the tic, as
            (club_id, trigger).

        Returns:
            A mapping from club identifiers to the assignments returned by
            their coach.
        """
        jobs: list[CoachJob] = []

        for club_id, trigger in triggers:
            participation = match.get_participation(club_id)

            if participation is None:
                continue

            if participation.coach_behavior_id is None:  # club plays without coach
                continue

            jobs.append(
                CoachJob(
                    club_id=club_id,
                    coach_behavior_id=participation.coach_behavior_id,
                    context=build_coach_context(
                        match,
                        participation,
                        trigger,
                    ),
                )
            )

        if not jobs:
            return {}

        results = self._worker_pool.execute_coach(
            jobs,
            match_id=self._match_id,
        )

        assignments: dict[int, list[Assignment]] = {}

        for job, job_assignments in zip(jobs, results):
            assignments.setdefault(job.club_id, []).extend(job_assignments)

        return assignments
