from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(user_name=current_user.club.name, user_email=current_user.email)


@router.post("", status_code=status.HTTP_201_CREATED)
def register_user(body: UserCreate, db: Annotated[Session, Depends(get_db)]) -> UserOut:
    try:
        user = user_service.register_user(db, body)
    except user_service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return UserOut(user_name=user.club.name, user_email=user.email)
