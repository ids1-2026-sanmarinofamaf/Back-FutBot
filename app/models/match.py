from __future__ import annotations

from typing import TYPE_CHECKING

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.match_participation import MatchParticipation


class MatchState(str, Enum):
    POR_COMENZAR = "POR_COMENZAR"
    JUGANDO = "JUGANDO"
    FINALIZADO = "FINALIZADO"


class Match(Base):
    __tablename__ = "matches"

    __table_args__ = (
        # the fixture order starts at 1
        CheckConstraint(
            "match_order IS NULL OR match_order >= 1",
            name="ck_match_order_positive"
        ),
        # the fechas start at 1
        CheckConstraint(
            "round IS NULL OR round >= 1",
            name="ck_match_round_positive"
        ),
    )

    # assigned from match_id_seq in the service, shared with friendly games
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    # null when the match does not belong to a league (friendly games)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True)
    state: Mapped[MatchState] = mapped_column(SAEnum(MatchState, name="match_state"), nullable=False, default=MatchState.POR_COMENZAR, server_default="POR_COMENZAR")
    # position in the drawn fixture
    match_order: Mapped[int | None] = mapped_column(nullable=True)
    # fecha of the fixture the match belongs to
    round: Mapped[int | None] = mapped_column(nullable=True)
    league: Mapped["League | None"] = relationship(back_populates="matches")
    participations: Mapped[list["MatchParticipation"]] = relationship(back_populates="match", cascade="all, delete-orphan", passive_deletes=True)
