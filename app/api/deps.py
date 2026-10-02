"""Dependencias compartidas por los routers."""

from typing import Annotated

from fastapi import Depends, HTTPException, status, WebSocketException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import auth_service

# auto_error=False para responder siempre 401 (y no 403) cuando falta el header
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    try:
        return auth_service.get_user_from_token(db, credentials.credentials)
    except auth_service.InvalidToken:
        raise credentials_exception

def get_current_user_ws(
          token: Annotated[str, Query()],
          db: Annotated[Session, Depends(get_db)]
) -> User:
        try:  
            return auth_service.get_user_from_token(db, token)
        except auth_service.InvalidToken: 
             raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)