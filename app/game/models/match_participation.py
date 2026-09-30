from dataclasses import dataclass

from app.game.models.player_in_match import PlayerInMatch


@dataclass  # non-persistent class
class MatchParticipation:
    club_id: int  # ID of the club to which that participation belongs
    roster_id: int  # ID of the roster to which that participation belongs

    players: list[PlayerInMatch]  # starting players and substitutes selected for this match

    goals: int = 0

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