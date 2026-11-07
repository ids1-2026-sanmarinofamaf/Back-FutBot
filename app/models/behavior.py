from app.models.base import CodeBehaviorBase

from sqlalchemy import ForeignKey, Boolean, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.player_on_roster import PlayerOnRoster
    from app.models.club import Club

class Behavior(CodeBehaviorBase):
    __tablename__ = "behaviors"

    __table_args__= (
        CheckConstraint(
            "(is_default = TRUE AND club_id IS NULL) "
            "OR (is_default = FALSE AND club_id IS NOT NULL)",
            name="ck_behavior_default_scope",
        ),
        UniqueConstraint("club_id", "name", name="uq_behavior_club_name"),
    )

    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id",ondelete="CASCADE"), nullable=True)

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    players_on_roster: Mapped[list["PlayerOnRoster"]] = relationship(back_populates="initial_behavior")

    club: Mapped["Club"] = relationship(back_populates="behaviors")
