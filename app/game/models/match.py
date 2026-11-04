
from dataclasses import dataclass
from enum import Enum

from app.game.models.ball import Ball, BallSnapshot
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatchSnapshot
from app.game.types import Side, Period

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

    current_period: Period = Period.FIRST_QUARTER
    side_a: Side = Side.LEFT
    side_b: Side = Side.RIGHT

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

    current_period: Period = Period.FIRST_QUARTER # actual period

    side_a: Side = Side.LEFT
    side_b: Side = Side.RIGHT

    substitution_requests_open: bool = True # it is set to true as long as substitutions can be planned.

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

            last_conceding_side=self.last_conceding_side,

            current_period=self.current_period,
            side_a=self.side_a,
            side_b=self.side_b
        )

    def plan_substitution(
        self,
        club_id: int,
        player_out_id: int,
        player_in_id: int,
    ) -> None:

        # validations related to the match
        if self.state != MatchState.IN_PROGRESS:
            raise ValueError("Match is not in progress")

        if not self.substitution_requests_open:
            raise ValueError("Substitution planning is closed")

        if self.participation_a.club_id == club_id:
            participation = self.participation_a
        elif self.participation_b.club_id == club_id:
            participation = self.participation_b
        else:
            raise PermissionError("Club is not participating")

        # we call the `plan substitution` method of `match participation` to carry it out
        participation.plan_substitution(
            player_out_id=player_out_id,
            player_in_id=player_in_id,
            period=self.current_period,
        )

    # method designed to be called later by the process that sets up the breaks
    def close_and_execute_substitutions(self) -> None:

        if self.state != MatchState.IN_PROGRESS:
            raise ValueError("Match is not in progress")

        if not self.substitution_requests_open:
            return

        # when we are executing a substitution, we close de requests
        self.substitution_requests_open = False

        period = self.current_period
        # execute the substitution
        self.participation_a.execute_pending_substitution(period)
        self.participation_b.execute_pending_substitution(period)

    # method designed to be called later by the process that sets up the breaks
    def start_next_period(self, next_period: Period) -> None:

        if self.substitution_requests_open:
            raise ValueError("Previous window is still open")

        if next_period.value != self.current_period.value + 1:
            raise ValueError("Invalid period transition")

        self.current_period = next_period

        self.participation_a.pending_substitution = None
        self.participation_b.pending_substitution = None

        self.substitution_requests_open = (next_period != Period.FOURTH_QUARTER)

    def switch_sides(self) -> None:
        self.side_a, self.side_b = self.side_b, self.side_a
        self.last_conceding_side = None

    # receives a SIDE, and returns the match participation contained within that SIDE
    # it will be used to determine which team scored a goal.
    def participation_defending(
        self,
        side: Side,
    ) -> MatchParticipation:
        if self.side_a == side:
            return self.participation_a

        if self.side_b == side:
            return self.participation_b

        raise ValueError("Invalid defending side")