"""Acceso a datos, todas las funciones reciben db: Session"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)

def create(db: Session, user: User) -> None:
    # Hace add, flush y refresh; el commit (o rollback) queda a cargo del service
    db.add(user)
    db.flush()
    db.refresh(user)  # Recarga el objeto desde la base

# def update_password(db, user, new_hash):
