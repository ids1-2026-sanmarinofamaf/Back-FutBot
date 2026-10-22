"""Script de siembra (seed) para desarrollo local y pruebas.
Crea un usuario con su club y 6 jugadores con stats base (PACSS=60).

Uso recomendado (crea ambas cuentas con sus jugadores):
    make seed

Uso manual individual (desde la raíz del repo):
    python -m scripts.create_user
    python -m scripts.create_user --email rival@futbot.com --password rival1234 --club "Rival FC"
    python -m scripts.create_user --email example@mail.com --password example1234 --club "Test FC" --players P1 P2 P3 P4 P5 P6
"""

import argparse

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models.club import Club
from app.models.player import Player
from app.models.user import User
from app.repositories import user_repository

DEFAULT_PLAYERS_BY_EMAIL = {
    "test@futbot.com": ["Andy", "Santiago", "Santino", "Lotu", "Joaco", "Luca"],
    "rival@futbot.com": ["Santi", "Julio", "Lean", "Chun", "Gonzalo", "Diego"],
}

DEFAULT_PACSS_VALUE = 60


def create_player_instance(name: str) -> Player:
    return Player(
        name=name,
        power=DEFAULT_PACSS_VALUE,
        agility=DEFAULT_PACSS_VALUE,
        control=DEFAULT_PACSS_VALUE,
        speed=DEFAULT_PACSS_VALUE,
        strength=DEFAULT_PACSS_VALUE,
    )


def main():
    parser = argparse.ArgumentParser(description="Crea un usuario de prueba con club y jugadores")
    parser.add_argument("--email", default="test@futbot.com")
    parser.add_argument("--password", default="test1234")
    parser.add_argument("--club", default="Test FC")
    parser.add_argument(
        "--players",
        nargs="*",
        default=None,
        help="Nombres de los jugadores a crear (PACSS=60 cada uno). Si no se especifica, se usan los defaults por email.",
    )
    args = parser.parse_args()

    player_names = (
        args.players
        if args.players is not None
        else DEFAULT_PLAYERS_BY_EMAIL.get(args.email, [])
    )

    db = SessionLocal()
    try:
        existing_user = user_repository.get_by_email(db, args.email)
        if existing_user is not None:
            if existing_user.club:
                existing_names = {p.name for p in existing_user.club.players}
                added = 0
                for name in player_names:
                    if name not in existing_names:
                        existing_user.club.players.append(create_player_instance(name))
                        added += 1
                if added > 0:
                    db.commit()
                    print(
                        f"Usuario {args.email} ya existía: se agregaron {added} jugadores a '{existing_user.club.name}'."
                    )
                else:
                    print(
                        f"Ya existe un usuario con email {args.email} y su club ya cuenta con los jugadores requeridos."
                    )
            else:
                print(f"Ya existe un usuario con email {args.email} sin club asociado.")
            return

        club = Club(name=args.club)
        for name in player_names:
            club.players.append(create_player_instance(name))

        user = User(
            email=args.email,
            hash_passwd=get_password_hash(args.password),
            club=club,
        )
        db.add(user)
        db.commit()
        print(
            f"Usuario creado: {args.email} / {args.password} (club: {args.club}) con {len(player_names)} jugadores: {', '.join(player_names)}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
