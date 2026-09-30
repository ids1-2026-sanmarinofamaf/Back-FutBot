from dataclasses import dataclass

from app.game.types import Position, Velocity
from app.game.models.runtime_behavior import RuntimeBehavior


@dataclass     # non-persistent class
class PlayerInMatch:
    player_id: int  # we don't use a player to build it, since it would increase coupling too much, because player uses a database

    position: Position
    velocity: Velocity
    starting_position: Position | None

    power: int      # repeat PACSS so we don't have to go fetch them from databases when we need them during the match
    agility: int 
    control: int 
    speed: int
    strength: int

    current_behavior: RuntimeBehavior | None     # it depends on whether he's on the field or not

    is_on_field: bool

    kick_cooldown_remaining: int = 0     # Remaining ticks for temporary restrictions applied to the player during the match     
    forced_wait_remaining: int = 0
    collision_penalty_remaining: int = 0