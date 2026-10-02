from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.club import Club

class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hash_passwd: Mapped[str] = mapped_column(String(255), nullable=False)

    club: Mapped["Club"] = relationship(back_populates="user", uselist=False,
                                        cascade="all, delete-orphan")
