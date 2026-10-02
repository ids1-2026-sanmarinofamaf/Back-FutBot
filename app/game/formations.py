from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot

# starting positions of each formation
FORMATION_POSITIONS = {
    Formation.DEFENSIVE: {
        RosterSlot.LEFT: (8.0, 5.0),
        RosterSlot.CENTER: (6.0, 10.0),
        RosterSlot.RIGHT: (8.0, 15.0),
    },

    Formation.OFFENSIVE: {
        RosterSlot.LEFT: (16.0, 5.0),
        RosterSlot.CENTER: (18.0, 10.0),
        RosterSlot.RIGHT: (16.0, 15.0),
    },
}