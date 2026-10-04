from app.game import primitives
from app.game.models.behavior_definition import BehaviorDefinition
from app.game.models.runtime_behavior import RuntimeBehavior


class BehaviorCompilationError(Exception):
    """Raised when a behavior cannot be compiled into a RuntimeBehavior."""


class BehaviorCompiler:
    """
    Compile behavior source code into an executable RuntimeBehavior.
    """

    def compile(
        self,
        behavior: BehaviorDefinition,
    ) -> RuntimeBehavior:
        namespace = self._build_namespace()

        try:
            exec(behavior.code, namespace)
        except Exception as exc:
            raise BehaviorCompilationError(
                f"Could not compile behavior {behavior.id}"
            ) from exc

        play = namespace.get("play")

        if not callable(play):
            raise BehaviorCompilationError(
                f"Behavior {behavior.id} does not define a callable play()"
            )

        return RuntimeBehavior(
            id=behavior.id,
            play=play,
        )

    def _build_namespace(self) -> dict:
        return {
            "self": primitives.self,
            "ball": primitives.ball,
            "teammates": primitives.teammates,
            "opponents": primitives.opponents,
            "score": primitives.score,
            "match_time_remaining": primitives.match_time_remaining,
            "current_period": primitives.current_period,
            "period_time_remaining": primitives.period_time_remaining,
            "starting_position": primitives.starting_position,
            "own_goal": primitives.own_goal,
            "opponent_goal": primitives.opponent_goal,
            "can_kick": primitives.can_kick,
            "tics_until_kick": primitives.tics_until_kick,
            "control_range": primitives.control_range,
            "can_move_distance": primitives.can_move_distance,
            "speed_for_distance": primitives.speed_for_distance,
            "can_kick_distance": primitives.can_kick_distance,
            "kick_force_for_distance": primitives.kick_force_for_distance,
            "distance": primitives.distance,
            "direction_to": primitives.direction_to,
            "next_ball_position": primitives.next_ball_position,
            "move": primitives.move,
            "kick": primitives.kick,
            "wait": primitives.wait,
        }