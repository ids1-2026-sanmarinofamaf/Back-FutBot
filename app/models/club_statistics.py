from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.club import Club

class ClubStatistics(Base):
    __tablename__ = "club_statistics"

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"),
        primary_key=True,
    )

    club: Mapped["Club"] = relationship(
        back_populates="statistics"
    )

    # we only use statistics from public leagues
    total_points: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_played: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_won: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_drawn: Mapped[int] = mapped_column(default=0, server_default="0")
    matches_lost: Mapped[int] = mapped_column(default=0, server_default="0")
    goals_for: Mapped[int] = mapped_column(default=0, server_default="0")
    goals_against: Mapped[int] = mapped_column(default=0, server_default="0")
    leagues_played: Mapped[int] = mapped_column(default=0, server_default="0")
    leagues_won: Mapped[int] = mapped_column(default=0, server_default="0")
