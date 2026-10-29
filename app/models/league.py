from __future__ import annotations

from typing import TYPE_CHECKING

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.club import Club
    from app.models.league_participation import LeagueParticipation
    from app.models.match import Match

class LeagueState(str, Enum):
    POR_COMENZAR = "POR_COMENZAR"
    INICIADA = "INICIADA"
    FINALIZADA = "FINALIZADA"


class LeaguePrivacy(str, Enum):
    PUBLICA = "PUBLICA"
    PRIVADA = "PRIVADA"


class League(Base):
    __tablename__ = "leagues"

    __table_args__ = (
        # ensure match duration and max clubs are positive
        CheckConstraint(
            "match_duration > 0",
            name="ck_league_match_duration_positive"
        ),
        CheckConstraint(
            "max_clubs >= 3",
            name="ck_league_max_clubs_min"
        ),
        # private leagues must have a password, public ones must not
        CheckConstraint(
            "(privacy = 'PRIVADA' AND password_hash IS NOT NULL) OR "
            "(privacy = 'PUBLICA' AND password_hash IS NULL)",
            name="ck_league_password_matches_privacy"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    match_duration: Mapped[int] = mapped_column(nullable=False)
    max_clubs: Mapped[int] = mapped_column(nullable=False)
    state: Mapped[LeagueState] = mapped_column(SAEnum(LeagueState, name="league_state"), nullable=False, default=LeagueState.POR_COMENZAR, server_default="POR_COMENZAR")
    privacy: Mapped[LeaguePrivacy] = mapped_column(SAEnum(LeaguePrivacy, name="league_privacy"), nullable=False)
    # only set for private leagues
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    creator: Mapped["Club"] = relationship("Club")
    league_participations: Mapped[list["LeagueParticipation"]] = relationship(back_populates="league", cascade="all, delete-orphan", passive_deletes=True,)
    matches: Mapped[list["Match"]] = relationship(back_populates="league", cascade="all, delete-orphan", passive_deletes=True, order_by="Match.match_order")
