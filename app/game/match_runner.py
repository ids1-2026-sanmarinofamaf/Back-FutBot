from typing import Protocol, Any
import time, asyncio

from app.game.models.match import Match, MatchState, MatchSnapshot
from app.game.constants import TIC_DURATION
from app.services.match_websocket_service import match_connection_manager, build_match_state_message


class BehaviorExecutorProtocol(Protocol):
    async def execute_all(self, snapshot: MatchSnapshot) -> Any:
        ...


class GameEngineProtocol(Protocol):
    def step(self, match: Match, snapshot: MatchSnapshot, actions: Any) -> None:
        ...

# since not all the classes are implemented yet, we use protocol to simulate them
class MatchRunner:
    def __init__(
        self,
        behavior_executor: BehaviorExecutorProtocol,
        game_engine: GameEngineProtocol,
    ):
        self.behavior_executor = behavior_executor
        self.game_engine = game_engine

# we implemented the execution of a single tick, and then the cycle of the whole match

    async def execute_tick(self, match: Match) -> None:  # async because we have to wait all the workers
        snapshot = match.snapshot()     # we make a copy of the match at a specific tick

        actions = await self.behavior_executor.execute_all(snapshot)    # through copying, we run all the behaviors, wait for the workers,
                                                                        # and save the actions each player needs to take

        self.game_engine.step(match,snapshot,actions)   # we update the match state, using the snapshot and actions

        match.current_tick += 1 # update the tick

        # new state after the tick
        new_snapshot = match.snapshot()

        # we format the received state
        message = build_match_state_message(new_snapshot)

        # we sent that new status to everyone connected
        await match_connection_manager.broadcast(match.match_id, message)

    async def run_match(self, match: Match) -> Match:
        # first, check that it's a valid match to start
        if match.state != MatchState.NOT_STARTED:
            raise ValueError("Match must be in NOT_STARTED state")

        if match.duration_ticks <= 0:
            raise ValueError("Match duration must be positive")

        # change the matchState and execute ticks
        match.state = MatchState.IN_PROGRESS

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


        