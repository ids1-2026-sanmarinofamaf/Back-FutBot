from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.behavior import Behavior
    from app.models.player import Player

class Club(Base):
    __tablename__ = "clubs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        unique=True, nullable=False,  # unique enforces the one-to-one relation in the database
    )
    name: Mapped[str] = mapped_column(String(30), nullable=False) 
    avatar: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    
    user: Mapped["User"] = relationship(back_populates="club")
    behaviors: Mapped[list["Behavior"]] = relationship(back_populates="club", cascade="all, delete-orphan")
    players: Mapped[list["Player"]] = relationship(back_populates="club", cascade="all, delete-orphan")
