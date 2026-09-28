from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot
from app.game.types import Position

# starting positions of each formation
FORMATION_POSITIONS = {
    Formation.DEFENSIVE: {
        RosterSlot.LEFT: Position(8.0, 5.0),
        RosterSlot.CENTER: Position(6.0, 10.0),
        RosterSlot.RIGHT: Position(8.0, 15.0),
    },

    Formation.OFFENSIVE: {
        RosterSlot.LEFT: Position(16.0, 5.0),
        RosterSlot.CENTER: Position(18.0, 10.0),
        RosterSlot.RIGHT: Position(16.0, 15.0),
    },
}