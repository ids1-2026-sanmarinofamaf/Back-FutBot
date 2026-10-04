from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.player import Player

class Club(Base):
    __tablename__ = "clubs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        unique=True, nullable=False,  # unique enforces the one-to-one relation in the database
    )
    name: Mapped[str] = mapped_column(String(30), nullable=False) 
    avatar: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    
    user: Mapped["User"] = relationship(back_populates="club")
    players: Mapped[list["Player"]] = relationship(back_populates="club", cascade="all, delete-orphan")