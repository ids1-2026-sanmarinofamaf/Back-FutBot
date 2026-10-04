from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.behavior import BehaviorOut
from app.services.behavior_service import list_behaviors

router = APIRouter(
    prefix="/clubes/me/behaviors",
    tags=["Behaviors"]
)


@router.get("", response_model=list[BehaviorOut])
def get_behaviors(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return list_behaviors(db=db, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
