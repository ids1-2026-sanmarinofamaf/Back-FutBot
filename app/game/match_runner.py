from typing import Protocol, Any

from app.game.models.match import Match


class BehaviorExecutorProtocol(Protocol):
    async def execute_all(self, snapshot: Match) -> Any:
        ...


class GameEngineProtocol(Protocol):
    def step(self, match: Match, actions: Any) -> Match:
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

async def execute_tick(self, match: Match) -> Match:  # async because we have to wait all the workers
    snapshot = match.snapshot()     # we make a copy of the match at a specific tick

    actions = await self.behavior_executor.execute_all(snapshot)    # through copying, we run all the behaviors, wait for the workers,
                                                                    # and save the actions each player needs to take

    next_match = self.game_engine.step(snapshot, actions)   # we pass the snapshot and the list of actions to the engine, 
                                                            # and it returns a new match with the actions executed
    

    return next_match 

