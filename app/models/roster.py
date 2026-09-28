from __future__ import annotations

from sqlalchemy import Enum as SAEnum # SAEnum is the enum for SQLAlquemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from enum import Enum


class Formation(str, Enum):  
    DEFENSIVE = "defensive"
    OFFENSIVE = "offensive"

class Roster(Base):
    __tablename__ = "rosters"

    id: Mapped[int] = mapped_column(  # column for ID
        primary_key=True
    )

    club_id: Mapped[int] = mapped_column(   # column to link the template to a certain club
        ForeignKey("clubs.id"),
        nullable=False
    )

    formation: Mapped[Formation] = mapped_column(  # column for the chosen roster
        SAEnum(Formation),          
        nullable=False
    )

    players: Mapped[list["PlayerOnRoster"]] = relationship(  # relationship with the players assigned to this roster
        "PlayerOnRoster",
        back_populates="roster",
        cascade="all, delete-orphan"  # delete associations when removed from the roster
    )