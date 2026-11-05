from dataclasses import dataclass, field

from app.game.models.player_in_match import PlayerInMatch
from app.game.models.pending_substitution import PendingSubstitution
from app.game.types import Period, Assignment


@dataclass  # non-persistent class
class MatchParticipation:
    club_id: int  # ID of the club to which that participation belongs
    roster_id: int  # ID of the roster to which that participation belongs

    players: list[PlayerInMatch]  # starting players and substitutes selected for this match

    coach_behavior_id: int | None = None  # coach (DT) behavior chosen in the roster, if any

    # behaviors the club can assign during the match, as name -> behavior id
    available_behaviors: dict[str, int] = field(default_factory=dict)

    # behavior changes waiting to be applied at the beginning of the next tick:
    # manual ones (player_id -> behavior_id) and the ones returned by the coach
    pending_behavior_changes: dict[int, int] = field(default_factory=dict)
    pending_coach_assignments: list[Assignment] = field(default_factory=list)

    goals: int = 0

    # each participation has its own pending substitution
    pending_substitution: PendingSubstitution | None = None
    # ensure only one substitution in one period
    last_substitution_period: Period | None = None

    # validations
    def __post_init__(self):
        if len(self.players) != 6:
            raise ValueError(
                "A match participation must have exactly 6 players"
            )

        starters = [
            player
            for player in self.players
            if player.is_on_field
        ]

        substitutes = [
            player
            for player in self.players
            if not player.is_on_field
        ]

        if len(starters) != 3:
            raise ValueError(
                "A match participation must have exactly 3 starters"
            )

        if len(substitutes) != 3:
            raise ValueError(
                "A match participation must have exactly 3 substitutes"
            ) 
             
        for i in range(len(self.players)):
            for j in range(i + 1, len(self.players)):
                if self.players[i].player_id == self.players[j].player_id:
                    raise ValueError(
                        "A match participation cannot contain duplicate players"
                    )  
    
    def get_player(self, player_id: int) -> PlayerInMatch | None:
        return next((p for p in self.players if p.player_id == player_id), None)


    def plan_substitution(
        self,
        player_out_id: int,
        player_in_id: int,
        period: Period,
    ) -> None:

        # when we are in the fourth period, changes can no longer be made
        if period not in (
            Period.FIRST_QUARTER,
            Period.SECOND_QUARTER,
            Period.THIRD_QUARTER,
        ):
            raise ValueError("No substitution available in this period")

        # only one substitution for period
        if self.last_substitution_period == period:
            raise ValueError("Substitution already executed in this period")

        # checks on the players involved
        outgoing = self.get_player(player_out_id)
        incoming = self.get_player(player_in_id)

        if outgoing is None or incoming is None:
            raise ValueError("Player does not belong to this participation")

        if not outgoing.is_on_field:
            raise ValueError("Outgoing player is not on field")

        if outgoing.starting_position is None:
            raise ValueError("Outgoing player has no starting position")

        if incoming.is_on_field:
            raise ValueError("Incoming player is not a substitute")

        # a valid request replaces the previous pending request.
        self.pending_substitution = PendingSubstitution(
            player_out_id=player_out_id,
            player_in_id=player_in_id,
            period=period,
        )

    # the manual change is not applied right away, so it can win over
    # the coach assignments of the same tick
    def plan_behavior_change(self, player_id: int, behavior_id: int) -> None:
        self.pending_behavior_changes[player_id] = behavior_id

    # called at the beginning of each tick; returns the coach assignments applied
    def apply_pending_behavior_changes(self) -> list[Assignment]:

        changes: dict[int, int] = {}
        applied_coach_assignments: dict[int, str] = {}

        # coach assignments: discard rivals, substitutes and unknown names
        for player_id, behavior_name in self.pending_coach_assignments:
            player = self.get_player(player_id)

            if player is None or not player.is_on_field:
                continue

            behavior_id = self.available_behaviors.get(behavior_name)

            if behavior_id is None:
                continue

            # if the coach assigns the same player twice, the last one wins
            changes[player_id] = behavior_id
            applied_coach_assignments[player_id] = behavior_name

        # manual changes go after, so they overwrite the coach
        for player_id, behavior_id in self.pending_behavior_changes.items():
            player = self.get_player(player_id)

            # the player may have been substituted since the request
            if player is None or not player.is_on_field:
                continue

            changes[player_id] = behavior_id
            applied_coach_assignments.pop(player_id, None)

        for player_id, behavior_id in changes.items():
            self.get_player(player_id).current_behavior_id = behavior_id

        self.pending_behavior_changes = {}
        self.pending_coach_assignments = []

        return list(applied_coach_assignments.items())

    # it should only be done once per period
    def execute_pending_substitution(self, period: Period) -> bool:

        pending = self.pending_substitution

        # no substituion on this period
        if pending is None:
            return False

        if pending.period != period:
            self.pending_substitution = None
            return False

        # cant execute 2 substitutions in 1 period
        if self.last_substitution_period == period:
            self.pending_substitution = None
            return False

        outgoing = self.get_player(pending.player_out_id)
        incoming = self.get_player(pending.player_in_id)

        # after a break, each player returns to their starting position
        incoming.position = outgoing.starting_position
        incoming.starting_position = outgoing.starting_position

        # inherit the current behavior from the outgoing player.
        incoming.current_behavior_id = outgoing.current_behavior_id

        # reset alll the temporary restrictions.
        incoming.kick_cooldown_remaining = 0
        incoming.forced_wait_remaining = 0
        incoming.collision_penalty_remaining = 0

        # update the active lineup.
        outgoing.is_on_field = False
        incoming.is_on_field = True

        outgoing.current_behavior_id = None

        # mark the period as used and remove the pending request.
        self.last_substitution_period = period
        self.pending_substitution = None

        return True
