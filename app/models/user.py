from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320)) # Email puede tener hasta 320 caracteres
    passwdhash: Mapped[str] = mapped_column(String(97)) # Argon2id genera un hash de hasta 97 caracteres
