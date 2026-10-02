from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

class Club(Base):
    __tablename__ = "club"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        unique=True, nullable=False,  # unique = garantiza el 1 a 1 en la base
    )
    name: Mapped[str] = mapped_column(String(30), nullable=False) 
    avatar: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    
    user: Mapped["User"] = relationship(back_populates="club")
