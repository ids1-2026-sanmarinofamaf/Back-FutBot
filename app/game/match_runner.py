from typing import Protocol, Any

from app.game.models.match import Match, MatchState, MatchSnapshot


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

        return match


    async def run_match(self, match: Match) -> Match:
        # first, check that it's a valid match to start
        if match.state != MatchState.NOT_STARTED:
            raise ValueError("Match must be in NOT_STARTED state")

        if match.duration_ticks <= 0:
            raise ValueError("Match duration must be positive")

        # change the matchState and execute ticks
        match.state = MatchState.IN_PROGRESS

        while match.current_tick < match.duration_ticks: 
            await self.execute_tick(match)

        # when the match ended, change its state to finished
        match.state = MatchState.FINISHED

        return match


        