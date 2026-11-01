from typing import Protocol, Any
import time, asyncio

from app.game.models.match import Match, MatchState, MatchSnapshot
from app.game.types import Assignment, CoachTrigger
from app.game.constants import TIC_DURATION
from app.services.match_websocket_service import (
    match_connection_manager,
    build_match_state_message,
    build_coach_changes_message,
)


class BehaviorCoordinatorProtocol(Protocol):
    def get_actions(self, snapshot: MatchSnapshot) -> Any:
        ...

    def get_coach_assignments(
        self,
        match: Match,
        triggers: list[tuple[int, CoachTrigger]],
    ) -> dict[int, list[Assignment]]:
        ...

class GameEngineProtocol(Protocol):
    def step(self, match: Match, snapshot: MatchSnapshot, actions: Any) -> None:
        ...

# since not all the classes are implemented yet, we use protocol to simulate them
class MatchRunner:
    def __init__(
        self,
        behavior_coordinator: BehaviorCoordinatorProtocol,
        game_engine: GameEngineProtocol,
    ):
        self.behavior_coordinator = behavior_coordinator
        self.game_engine = game_engine

# we implemented the execution of a single tick, and then the cycle of the whole match

    async def execute_tick(self, match: Match) -> None:  # async because we have to wait all the workers
        # apply the behavior changes requested since the last tick (coach and manual)
        applied_assignments = match.apply_pending_behavior_changes()

        # notify the coach changes, only if some coach assignment was applied
        if any(applied_assignments.values()):
            await match_connection_manager.broadcast(
                match.match_id,
                build_coach_changes_message(applied_assignments, match.current_tick),
            )

        snapshot = match.snapshot()     # we make a copy of the match at a specific tick

        actions = self.behavior_coordinator.get_actions(snapshot)    # through copying, we run all the behaviors, wait for the workers,
                                                                        # and save the actions each player needs to take

        self.game_engine.step(match,snapshot,actions)   # we update the match state, using the snapshot and actions

        match.current_tick += 1 # update the tick

        # run the coaches triggered during this tick (goals, period start)
        self._execute_coaches(match)

        # new state after the tick
        new_snapshot = match.snapshot()

        # we format the received state
        message = build_match_state_message(new_snapshot)

        # we sent that new status to everyone connected
        await match_connection_manager.broadcast(match.match_id, message)

    def _execute_coaches(self, match: Match) -> None:
        # take the triggers and empty the list, so each event runs the coach only once
        triggers = match.pending_coach_triggers
        match.pending_coach_triggers = []

        if not triggers:
            return

        assignments = self.behavior_coordinator.get_coach_assignments(
            match,
            triggers,
        )

        # keep them for the next tick, where they are validated and applied
        for club_id, club_assignments in assignments.items():
            match.get_participation(club_id).pending_coach_assignments.extend(
                club_assignments
            )

    async def run_match(self, match: Match) -> Match:
        # first, check that it's a valid match to start
        if match.state != MatchState.NOT_STARTED:
            raise ValueError("Match must be in NOT_STARTED state")

        if match.duration_ticks <= 0:
            raise ValueError("Match duration must be positive")

        # change the matchState and execute ticks
        match.state = MatchState.IN_PROGRESS

        # the first period starts with the match, so the coaches run before
        # the first tick and their assignments apply from that tick
        match.register_period_start_triggers()
        self._execute_coaches(match)

        # send the initial state of the match before executing the first tick
        initial_snapshot = match.snapshot()

        initial_message = build_match_state_message(initial_snapshot)

        await match_connection_manager.broadcast(match.match_id,initial_message)

        while match.current_tick < match.duration_ticks:
            # start the tick
            tick_start = time.monotonic()
            # execute the tick and all the workers
            await self.execute_tick(match)

            # then we have to check if the tick ends before the TIC_DURATION
            elapsed = time.monotonic() - tick_start

            remaining_time = TIC_DURATION - elapsed
            # if the tick ends before TIC_DURATION, we hae to wait the remaining_time
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)

        # when the match ended, change its state to finished and close ws conections
        match.state = MatchState.FINISHED

        await match_connection_manager.close_match_connection(match.match_id)   

        return match


        