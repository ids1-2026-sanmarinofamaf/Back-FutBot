from app.database import Base

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.player_on_roster import PlayerOnRoster
    from app.models.club import Club

class Behavior(Base):
    __tablename__ = "behaviors"
    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id",ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)

    players_on_roster: Mapped[list["PlayerOnRoster"]] = relationship(back_populates="initial_behavior")

    club: Mapped["Club"] = relationship(back_populates="behaviors")