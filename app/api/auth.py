from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/sessions")
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    try:
        token = auth_service.login(db, body.email, body.password)
    except auth_service.InvalidCredentials:
        # Mismo error si el email no existe o la contraseña esta mal
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(token=token)
