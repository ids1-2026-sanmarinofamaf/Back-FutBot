from dataclasses import dataclass
from enum import Enum

from app.game.models.ball import Ball, BallSnapshot
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatchSnapshot
from app.game.types import Side

class MatchState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"

# we use snapshots of ball and player in match to make sure we work with immutable values
@dataclass(frozen=True)
class MatchSnapshot:
    players_a: tuple[PlayerInMatchSnapshot, ...]
    players_b: tuple[PlayerInMatchSnapshot, ...]

    ball: BallSnapshot

    duration_ticks: int
    current_tick: int

    score_a: int
    score_b: int

    last_conceding_side: Side | None

@dataclass  # non-persistent class
class Match:
    match_id: int   # it will be used for WebSockets.
    participation_a: MatchParticipation
    participation_b: MatchParticipation
    ball: Ball

    duration_ticks: int  # total duration of the match expressed in simulation ticks

    current_tick: int = 0

    last_conceding_side: Side | None = None

    state: MatchState = MatchState.NOT_STARTED

    def snapshot(self) -> MatchSnapshot:  # returns a copy of match in the state it was in when made
        return MatchSnapshot(
            # we get the status of the players from each team at a certain tick
            players_a=tuple(
                player.snapshot()
                for player in self.participation_a.players
            ),
            players_b=tuple(
                player.snapshot()
                for player in self.participation_b.players
            ),
            # we get the state of the ball for each team at a certain tick
            ball=self.ball.snapshot(),

            duration_ticks=self.duration_ticks,
            current_tick=self.current_tick,
            # we get the scores of each team at a ceratin tick
            score_a=self.participation_a.goals,
            score_b=self.participation_b.goals,

            last_conceding_side=self.last_conceding_side
        )