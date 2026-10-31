from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.club import ClubOut, ClubUpdate
from app.services import club_service


router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("/me", response_model=ClubOut)
def get_my_club(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return club_service.get_club(db, current_user.id)

    except club_service.ClubNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found"
        )

@router.put("/me", status_code=status.HTTP_204_NO_CONTENT)
def update_my_club(
    data: ClubUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        club_service.update_club(
            db=db,
            user_id=current_user.id,
            data=data
        )

    except club_service.ClubNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found"
        )
