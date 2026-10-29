from __future__ import annotations

from typing import TYPE_CHECKING

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.club import Club
    from app.models.roster import Roster


class MatchRole(str, Enum):
    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"


class MatchParticipation(Base):
    __tablename__ = "match_participations"

    __table_args__ = (
        # one local and one visitor per match
        UniqueConstraint("match_id", "role", name="uq_match_role"),
        # a club cannot play against itself
        UniqueConstraint("match_id", "club_id", name="uq_match_club"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    # the roster generated for the league, not the club's default one
    roster_id: Mapped[int] = mapped_column(ForeignKey("rosters.id"), nullable=False)
    role: Mapped[MatchRole] = mapped_column(SAEnum(MatchRole, name="match_role"), nullable=False)
    match: Mapped["Match"] = relationship(back_populates="participations")
    club: Mapped["Club"] = relationship("Club")
    roster: Mapped["Roster"] = relationship("Roster")
