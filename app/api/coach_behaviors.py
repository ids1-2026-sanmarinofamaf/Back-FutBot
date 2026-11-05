from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.coach_behavior import CoachBehaviorIn, CoachBehaviorOut
from app.services.coach_behavior_service import (
    list_coach_behaviors,
    get_coach_behavior,
    create_coach_behavior,
    delete_coach_behavior,
    ClubNotFound,
    ClubInActiveMatch,
    CoachBehaviorNameTaken,
    InvalidCoachCode,
    CoachBehaviorNotFound,
)


router = APIRouter(
    prefix="/clubes/me/coach_behaviors",
    tags=["Coach Behaviors"]
)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CoachBehaviorOut)
def create(
    data: CoachBehaviorIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_coach_behavior(
            db=db,
            user_id=current_user.id,
            name=data.name,
            code=data.code,
        )

    except ClubNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    except ClubInActiveMatch as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )

    except CoachBehaviorNameTaken as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    except InvalidCoachCode as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.get("", response_model=list[CoachBehaviorOut])
def get_coach_behaviors(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_coach_behaviors(db=db, user_id=current_user.id)

    except ClubNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@router.get("/{coach_behavior_id}", response_model=CoachBehaviorOut)
def get_coach_behavior_by_id(
    coach_behavior_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_coach_behavior(
            db=db,
            user_id=current_user.id,
            coach_behavior_id=coach_behavior_id,
        )

    except (ClubNotFound, CoachBehaviorNotFound) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@router.delete("/{coach_behavior_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    coach_behavior_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_coach_behavior(
            db=db,
            user_id=current_user.id,
            coach_behavior_id=coach_behavior_id,
        )

    except (ClubNotFound, CoachBehaviorNotFound) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    except ClubInActiveMatch as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
