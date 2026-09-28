from __future__ import annotations

from sqlalchemy import Boolean, Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from enum import Enum


class RosterSlot(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"

class PlayerOnRoster(Base):
    __tablename__ = "players_on_roster"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    roster_id: Mapped[int] = mapped_column(
        ForeignKey("rosters.id"),           # reference to the roster it belongs to
        nullable=False
    )

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),           # reference to the player it belongs to
        nullable=False
    )

    is_starter: Mapped[bool] = mapped_column(
        Boolean,           
        nullable=False
    )

    slot: Mapped[RosterSlot | None] = mapped_column(        # it only takes up a slot if it's a starter, otherwise nothing
        SAEnum(RosterSlot),
        nullable=True
    )

    initial_behavior_id: Mapped[int | None] = mapped_column(         # it only takes up a behavior if it's a starter, otherwise nothing
        ForeignKey("behaviors.id"),         # reference to the behavior it belongs to
        nullable=True
    )

    roster: Mapped["Roster"] = relationship(            # relationship to the parent roster
        "Roster",
        back_populates="players"
    )

    player: Mapped["Player"] = relationship(            # relationship to the referenced player
        "Player"
    )

    initial_behavior: Mapped["Behavior | None"] = relationship(         # relationship to the initial behavior
        "Behavior"
    )