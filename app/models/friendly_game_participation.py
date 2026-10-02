from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FriendlyGameRole(str, Enum):
    CREATOR = "CREATOR"
    GUEST = "GUEST"


class FriendlyGameParticipation(Base):
    __tablename__ = "friendly_game_participations"

        # ensure that the same club cannot participate more than once
        # in the same friendly game
    __table_args__ = (
        UniqueConstraint(
            "friendly_game_id",
            "club_id",
            name="uq_friendly_game_club"
        ),
        # Ensure that there can only be one participant per role
        # in the same friendly game
        UniqueConstraint(
            "friendly_game_id",
            "role",
            name="uq_friendly_game_role"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    friendly_game_id: Mapped[int] = mapped_column(
        ForeignKey("friendly_games.id"),
        nullable=False
    )

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
    )

    roster_id: Mapped[int] = mapped_column(
        ForeignKey("rosters.id"),
        nullable=False
    )

    role: Mapped[FriendlyGameRole] = mapped_column(
        SAEnum(FriendlyGameRole),
        nullable=False
    )

    friendly_game: Mapped["FriendlyGame"] = relationship(
        "FriendlyGame",
        back_populates="participations"
    )

    club: Mapped["Club"] = relationship(
        "Club"
    )

    roster: Mapped["Roster"] = relationship(
        "Roster"
    )