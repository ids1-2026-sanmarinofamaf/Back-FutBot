from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#if TYPE_CHECKING:
#    from app.models.club import sarasa


class League(Base):
    __tablename__= "leagues"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    match_duration: Mapped[int] = mapped_column(unique=True, nullable=False)
    mas_amount: Mapped[int] = mapped_column(unique=True, nullable=False)
    state: Mapped[enumerate] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(unique=True, nullable=False)
    privacy: Mapped[enumerate] = mapped_column(nullable=False)

    # tiene que estar ligada al club que la crea supong y al match_participation: relationship() ver luego