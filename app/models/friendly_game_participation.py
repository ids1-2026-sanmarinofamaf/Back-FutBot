from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FriendlyGameParticipation(Base):
    __tablename__ = "friendly_game_participations"

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