from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db

from app.schemas.behavior_preview import (
    BehaviorPreviewCreate,
    BehaviorPreviewCreateResponse,
)

from app.services.behavior_preview_service import (
    create_preview,
    stop_preview,
)


router = APIRouter(
    prefix="/clubes/me/behaviors/previews",
    tags=["Behavior Previews"],
)


@router.post(
    "",
    response_model=BehaviorPreviewCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    data: BehaviorPreviewCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        preview_id = create_preview(
            db=db,
            user_id=current_user.id,
            code=data.code,
            behavior_teammate_1=data.behavior_teammate_1,
            behavior_teammate_2=data.behavior_teammate_2,
        )

        return BehaviorPreviewCreateResponse(
            preview_id=preview_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete(
    "/{preview_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    preview_id: UUID,
    current_user=Depends(get_current_user),
):
    try:
        stop_preview(
            preview_id=preview_id,
            user_id=current_user.id,
        )

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from error
