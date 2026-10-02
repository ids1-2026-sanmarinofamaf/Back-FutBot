"""Logica de autenticacion: login y obtener el usuario a partir del token."""

import jwt
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User
from app.repositories import user_repository


class InvalidCredentials(Exception):
    """Email o contraseña incorrectos (no se distingue cual a proposito)."""


class InvalidToken(Exception):
    """Token vencido, con firma invalida o de un usuario que ya no existe."""


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = user_repository.get_by_email(db, email)
    if user is None:
        security.verify_password(password, security.DUMMY_HASH)  # mismo tiempo de respuesta exista o no
        return None
    if not security.verify_password(password, user.hash_passwd):
        return None
    return user


def login(db: Session, email: str, password: str) -> str:
    user = authenticate_user(db, email, password)
    if user is None:
        raise InvalidCredentials()
    return security.create_access_token(user.email)


def get_user_from_token(db: Session, token: str) -> User:
    try:
        email = security.decode_access_token(token)
    except jwt.InvalidTokenError:
        raise InvalidToken()
    user = user_repository.get_by_email(db, email)
    if user is None:
        raise InvalidToken()
    return user
