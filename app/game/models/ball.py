from dataclasses import dataclass

from app.game.types import Position, Velocity


@dataclass  # non-persistent class
class Ball:
    position: Position
    velocity: Velocity