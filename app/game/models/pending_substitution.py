from dataclasses import dataclass

from app.game.types import Period


@dataclass(frozen=True)
class PendingSubstitution:
    player_out_id: int
    player_in_id: int
    period: Period
