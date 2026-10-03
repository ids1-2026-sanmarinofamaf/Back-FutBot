"""Crea un usuario (con su club) en la base de desarrollo, para poder loguearse mientras no
exista el endpoint de registro.

Uso (desde la raíz del repo):
    python -m scripts.create_user
    python -m scripts.create_user --email ana@mail.com --password otra1234 --club "Ana FC"
"""

import argparse

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models.club import Club
from app.models.user import User
from app.repositories import user_repository


def main():
    parser = argparse.ArgumentParser(description="Crea un usuario de prueba")
    parser.add_argument("--email", default="test@futbot.com")
    parser.add_argument("--password", default="test1234")
    parser.add_argument("--club", default="Test FC")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if user_repository.get_by_email(db, args.email) is not None:
            print(f"Ya existe un usuario con email {args.email}")
            return
        user = User(
            email=args.email,
            hash_passwd=get_password_hash(args.password),
            club=Club(name=args.club),
        )
        db.add(user)
        db.commit()
        print(f"Usuario creado: {args.email} / {args.password} (club: {args.club})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
