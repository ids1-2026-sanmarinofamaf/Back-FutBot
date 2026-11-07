from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import CodeBehaviorBase

if TYPE_CHECKING:
    from app.models.club import Club
    from app.models.roster import Roster


class CoachBehavior(CodeBehaviorBase):
    __tablename__ = "coach_behaviors"

    __table_args__ = (
        UniqueConstraint("club_id", "name", name="uq_coach_behavior_club_name"),
    )

    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)

    club: Mapped["Club"] = relationship(back_populates="coach_behaviors")
    rosters: Mapped[list["Roster"]] = relationship(back_populates="coach_behavior")
