from dataclasses import dataclass

from app.game.types import Position, Velocity

# snapshot for playerInMatch because it's needed for matchsnapshot
@dataclass(frozen=True)
class PlayerInMatchSnapshot:
    player_id: int

    position: Position
    velocity: Velocity
    starting_position: Position | None

    power: int
    agility: int
    control: int
    speed: int
    strength: int

    current_behavior_id: int | None
    is_on_field: bool

    kick_cooldown_remaining: int
    forced_wait_remaining: int
    collision_penalty_remaining: int

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

    current_behavior_id: int | None     # it depends on whether he's on the field or not

    is_on_field: bool

    kick_cooldown_remaining: int = 0     # Remaining ticks for temporary restrictions applied to the player during the match     
    forced_wait_remaining: int = 0
    collision_penalty_remaining: int = 0

    def snapshot(self) -> PlayerInMatchSnapshot:
            return PlayerInMatchSnapshot(
                    player_id=self.player_id,
                    position=self.position,
                    velocity=self.velocity,
                    starting_position=self.starting_position,
                    power=self.power,
                    agility=self.agility,
                    control=self.control,
                    speed=self.speed,
                    strength=self.strength,
                    current_behavior_id=self.current_behavior_id,
                    is_on_field=self.is_on_field,
                    kick_cooldown_remaining=self.kick_cooldown_remaining,
                    forced_wait_remaining=self.forced_wait_remaining,
                    collision_penalty_remaining=self.collision_penalty_remaining,
                )