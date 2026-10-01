from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FriendlyGameState(str, Enum):
    POR_COMENZAR = "POR_COMENZAR"
    JUGANDO = "JUGANDO"
    FINALIZADO = "FINALIZADO"


class FriendlyGame(Base):
    __tablename__ = "friendly_games"

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
        ForeignKey("user_account.id"),
        nullable=False
    )

    creator: Mapped["User"] = relationship(
        "User"
    )

    participations: Mapped[list["FriendlyGameParticipation"]] = relationship(
        "FriendlyGameParticipation",
        back_populates="friendly_game",
        cascade="all, delete-orphan"
    )

    def validate_participations(self):
        if len(self.participations) > 2:
            raise ValueError(
                "A friendly game cannot have more than 2 participants"
            )