"""Logica de registro de usuarios."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.models.club import DEFAULT_AVATAR, Club
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import UserCreate


class EmailAlreadyRegistered(Exception):
    """El email que has ingresado ya esta en uso."""


def validate_email_in_use(db: Session, email: str) -> None:
    if user_repository.get_by_email(db, email) is not None:
        raise EmailAlreadyRegistered()


def register_user(db: Session, data: UserCreate) -> User:
    
    # Si el email ya existe se aborta antes de instanciar nada
    validate_email_in_use(db, data.email)

    user = User(
        email=data.email,
        hash_passwd=security.get_password_hash(data.password),
    )
    # El cascade de User.club persiste el club junto con el usuario
    user.club = Club(name=data.club_name, avatar=data.avatar or DEFAULT_AVATAR)

    try:
        user_repository.create(db, user)
        db.commit()
    except IntegrityError:
        # Dos registros simultaneos con el mismo email: el unique de la base frena al segundo
        db.rollback()
        raise EmailAlreadyRegistered()
    except Exception:
        # Cualquier otro fallo (ej: DataError por el largo de avatar): no deja residuos
        db.rollback()
        raise

    return user
