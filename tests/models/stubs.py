from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# create these basic classes to test roster-related functionality.
class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(primary_key=True)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)


class Behavior(Base):
    __tablename__ = "behaviors"

    id: Mapped[int] = mapped_column(primary_key=True)