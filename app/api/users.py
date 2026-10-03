from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(tags=["users"])

#@router.post("/users")
#def register_user(UserCreate):


@router.get("/users/me")
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(user_name=current_user.club.name, user_email=current_user.email)
