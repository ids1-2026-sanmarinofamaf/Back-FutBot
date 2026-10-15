from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.club import Club 

class LeagueParticipation(Base):
    __tablename__ = "league_participations"

    __table_args__ = (
        CheckConstraint(
            "matches_won >= 0 AND matches_drawn >= 0 AND matches_lost >= 0 "
            "AND goals_for >= 0 AND goals_against >= 0",
            name="ck_league_participation_non_negative",
        ),
        # played matches must equal won + drawn + lost
        CheckConstraint(
            "matches_played = matches_won + matches_drawn + matches_lost",
            name="ck_league_participation_matches_played",
        ),
        # points follow the 3/1/0 rule
        CheckConstraint(
            "points = 3 * matches_won + matches_drawn",
            name="ck_league_participation_points",
        ),
    )

    # composite PK: a club joins a given league only once
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True)
    points: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_played: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_won: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_drawn: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_lost: Mapped[int] = mapped_column(default=0, server_default="0")
    goals_for: Mapped[int] = mapped_column(default=0, server_default="0")
    goals_against: Mapped[int] = mapped_column(default=0, server_default="0")
    league: Mapped["League"] = relationship(back_populates="league_participations")
    club: Mapped["Club"] = relationship(back_populates="league_participations")