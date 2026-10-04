from __future__ import annotations

from sqlalchemy import Enum as SAEnum # SAEnum is the enum for SQLAlquemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from enum import Enum


class Formation(str, Enum):  
    DEFENSIVE = "defensive"
    OFFENSIVE = "offensive"

class Roster(Base):
    __tablename__ = "rosters"

    id: Mapped[int] = mapped_column(  # column for ID
        primary_key=True
    )

    club_id: Mapped[int] = mapped_column(   # column to link the template to a certain club
        ForeignKey("clubs.id"),
        nullable=False
    )

    formation: Mapped[Formation] = mapped_column(  # column for the chosen roster
        SAEnum(Formation),          
        nullable=False
    )

    players: Mapped[list["PlayerOnRoster"]] = relationship(  # relationship with the players assigned to this roster
        "PlayerOnRoster",
        back_populates="roster",
        cascade="all, delete-orphan"  # delete associations when removed from the roster
    )

    # validations
    def validate_roster(self):
        if len(self.players) != 6:
            raise ValueError(
                "A roster must have exactly 6 players"
            )

        if sum(player.is_starter for player in self.players) != 3:
            raise ValueError(
                "A roster must have exactly 3 starters and 3 substitutes"
            )

        # no duplicate players
        player_ids = [player.player_id for player in self.players]

        if len(player_ids) != len(set(player_ids)):
            raise ValueError(
                "A roster cannot contain duplicate players"
            )

        # individual validations
        for player in self.players:
            if player.is_starter:
                if player.slot is None:
                    raise ValueError(
                        "A starter must have a roster slot"
                    )

                if player.initial_behavior_id is None:
                    raise ValueError(
                        "A starter must have an initial behavior"
                    )

            else:
                if player.slot is not None:
                    raise ValueError(
                        "A substitute cannot have a roster slot"
                    )

                if player.initial_behavior_id is not None:
                    raise ValueError(
                        "A substitute cannot have an initial behavior"
                    )

        # starter slots must be unique
        starter_slots = [
            player.slot
            for player in self.players
            if player.is_starter
        ]

        if len(starter_slots) != len(set(starter_slots)):
            raise ValueError(
                "Starter roster slots must be unique"
            )
                    