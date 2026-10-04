from sqlalchemy import String, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.club import Club

class Player(Base):
    __tablename__= "players"

    # ensure stats are within valid range and their total does not exceed the limit
    __table_args__ = (
        CheckConstraint("power BETWEEN 20 AND 100", name="ck_player_power_range"),
        CheckConstraint("agility BETWEEN 20 AND 100", name="ck_player_agility_range"),
        CheckConstraint("control BETWEEN 20 AND 100", name="ck_player_control_range"),
        CheckConstraint("speed BETWEEN 20 AND 100", name="ck_player_speed_range"),
        CheckConstraint("strength BETWEEN 20 AND 100", name="ck_player_strength_range"),
        CheckConstraint(
            "power + agility + control + speed + strength <= 300",
            name="ck_player_total_stats",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"),nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    power: Mapped[int] = mapped_column(nullable=False)
    agility: Mapped[int] = mapped_column(nullable=False)
    control: Mapped[int] = mapped_column(nullable=False)
    speed: Mapped[int] = mapped_column(nullable=False)
    strength: Mapped[int]= mapped_column(nullable=False)

    club: Mapped["Club"] = relationship(back_populates="players")