from dataclasses import dataclass
from enum import Enum
import copy

from app.game.models.ball import Ball
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatch

class MatchState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"

@dataclass(frozen=True)
class MatchSnapshot:
    players_a: tuple[PlayerInMatch, ...]
    players_b: tuple[PlayerInMatch, ...]

    ball: Ball

    duration_ticks: int
    current_tick: int

    score_a: int
    score_b: int

@dataclass  # non-persistent class
class Match:
    match_id: int   # it will be used for WebSockets.
    participation_a: MatchParticipation
    participation_b: MatchParticipation
    ball: Ball

    duration_ticks: int  # Total duration of the match expressed in simulation ticks

    current_tick: int = 0

    state: MatchState = MatchState.NOT_STARTED

    def snapshot(self) -> MatchSnapshot:  # returns a copy of match in the state it was in when made
        return MatchSnapshot(
            players_a=tuple(
                copy.deepcopy(self.participation_a.players)
            ),
            players_b=tuple(
                copy.deepcopy(self.participation_b.players)
            ),
            ball=copy.deepcopy(self.ball),
            duration_ticks=self.duration_ticks,
            current_tick=self.current_tick,
            score_a=self.participation_a.goals,
            score_b=self.participation_b.goals,
        )



    