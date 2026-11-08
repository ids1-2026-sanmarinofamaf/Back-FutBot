from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CodeBehaviorBase(Base):
    """Shared columns for user-written code behaviors (player and coach)."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
