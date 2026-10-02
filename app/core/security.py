"""Criptografia y JWT. Sin HTTP ni base de datos."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Falta la variable de entorno SECRET_KEY")

ALGORITHM = "HS256" # Algoritmo para firmar el token
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # vida del access token


password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummypassword")

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

def create_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid4()),
        "iat": now,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> str:
    """Devuelve el email (sub) del token.

    Lanza jwt.InvalidTokenError si la firma es invalida, el token vencio
    (ExpiredSignatureError es subclase) o faltan claims.
    """
    payload = jwt.decode(
        token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["sub", "exp", "jti"]}
    )
    return payload["sub"]
