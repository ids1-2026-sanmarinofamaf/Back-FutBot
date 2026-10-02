from sqlalchemy.orm import Session

from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster
from app.schemas.roster import RosterCreate

# create a Roster in db with data
def create(db: Session, club_id: int, data: RosterCreate) -> Roster:
    # create the roster object associated with the club
    roster = Roster(club_id=club_id, formation=data.formation)

    roster.players = [
        PlayerOnRoster(
            player_id=player.player_id,
            is_starter=player.is_starter,
            slot=player.slot,
            initial_behavior_id=player.initial_behavior_id
        )
        for player in data.players
    ]
    # Register the roster in the current DB session
    db.add(roster)
    # use flush instead of commit to keep transaction control outside this function, so we can rollback later
    db.flush()

    return roster