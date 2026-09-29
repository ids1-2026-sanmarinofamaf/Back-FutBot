from dataclasses import dataclass
from enum import Enum
import copy

from app.game.models.ball import Ball
from app.game.models.match_participation import MatchParticipation

class MatchState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"

@dataclass  # non-persistent class
class Match:
    match_id: int   # it will be used for WebSockets.
    participation_a: MatchParticipation
    participation_b: MatchParticipation
    ball: Ball

    duration_ticks: int  # Total duration of the match expressed in simulation ticks

    current_tick: int = 0

    state: MatchState = MatchState.NOT_STARTED

    def snapshot(self) -> "Match":  # returns a copy of match in the state it was in when made
        return copy.deepcopy(self)