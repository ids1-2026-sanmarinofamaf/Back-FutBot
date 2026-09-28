from dataclasses import dataclass

from app.game.models.player_in_match import PlayerInMatch


@dataclass  # non-persistent class
class MatchParticipation:
    club_id: int  # ID of the club to which that participation belongs
    roster_id: int  # ID of the roster to which that participation belongs

    players: list[PlayerInMatch]  # starting players and substitutes selected for this match

    goals: int = 0