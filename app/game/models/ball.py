from dataclasses import dataclass

from app.game.types import Position, Velocity

# snapshot for Ball because it's needed for matchsnapshot
@dataclass(frozen=True)
class BallSnapshot:
    position: Position
    velocity: Velocity

@dataclass  # non-persistent class
class Ball:
    position: Position
    velocity: Velocity

    def snapshot(self) -> BallSnapshot:
        return BallSnapshot(
            position=self.position,
            velocity=self.velocity,
        )
