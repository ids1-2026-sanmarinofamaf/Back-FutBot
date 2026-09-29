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
