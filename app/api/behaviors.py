
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.behavior import BehaviorOut, BehaviorCodeOut
from app.services.behavior_service import (
    list_behaviors,
    get_behavior,
    get_behavior_by_name,
)


router = APIRouter(
    prefix="/clubes/me/behaviors",
    tags=["Behaviors"]
)


@router.get("", response_model=list[BehaviorOut] | BehaviorCodeOut)
def get_behaviors(
    name: str | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if name is None:
            return list_behaviors(db=db, user_id=current_user.id)

        behavior = get_behavior_by_name(
            db=db,
            user_id=current_user.id,
            name=name,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    if behavior is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Behavior not found",
        )

    return behavior


# get a behavior by ID for the authenticated user
@router.get("/{behavior_id}", response_model=BehaviorOut)
def get_behavior_by_id(
    behavior_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_behavior(
            db=db,
            user_id=current_user.id,
            behavior_id=behavior_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
