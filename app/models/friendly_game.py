from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FriendlyGameState(str, Enum):
    POR_COMENZAR = "POR_COMENZAR"
    JUGANDO = "JUGANDO"
    FINALIZADO = "FINALIZADO"


class FriendlyGame(Base):
    __tablename__ = "friendly_games"

    # ensure duration is positive
    __table_args__ = (
        CheckConstraint(
            "duration > 0",
            name="ck_friendly_game_duration_positive"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    duration: Mapped[int] = mapped_column(
        nullable=False
    )

    state: Mapped[FriendlyGameState] = mapped_column(
        SAEnum(FriendlyGameState),
        nullable=False,
        default=FriendlyGameState.POR_COMENZAR
    )

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
    )

    creator: Mapped["Club"] = relationship(
        "Club"
    )

    participations: Mapped[list["FriendlyGameParticipation"]] = relationship(
        "FriendlyGameParticipation",
        back_populates="friendly_game",
        cascade="all, delete-orphan"
    )