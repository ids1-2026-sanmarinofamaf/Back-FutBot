
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.behavior import (
    BehaviorOut,
    BehaviorCodeOut,
    BehaviorIn,
    BehaviorCreateOut,
    BehaviorValidateIn,
    BehaviorValidateOut,
)
from app.services.behavior_service import (
    list_behaviors,
    get_behavior,
    get_behavior_by_name,
    validate_behavior,
    create_behavior,
    update_behavior,
    BehaviorValidationError,
    DefaultBehaviorModificationError,
)


router = APIRouter(
    prefix="/clubes/me/behaviors",
    tags=["Behaviors"]
)

@router.post(
    "/validate",
    response_model=BehaviorValidateOut,
    status_code=status.HTTP_200_OK,
)
def validate_behavior_endpoint(
    data: BehaviorValidateIn,
    current_user=Depends(get_current_user),
):
    """
    Validate behavior Python source code for the authenticated user.

    Args:
        data: Request payload containing the behavior source code.
        current_user: Currently authenticated user injected by dependency.

    Returns:
        BehaviorValidateOut indicating that the code is valid.

    Raises:
        HTTPException: 400 Bad Request if the behavior code fails validation.
    """
    try:
        is_valid = validate_behavior(code=data.code)
        return BehaviorValidateOut(valid=is_valid)
    except BehaviorValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

@router.post(
    "",
    response_model=BehaviorCreateOut,
    status_code=status.HTTP_201_CREATED,
)
def create_behavior_endpoint(
    data: BehaviorIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new custom behavior for the authenticated user's club.

    Args:
        data: Request payload containing behavior name and Python source code.
        current_user: Currently authenticated user injected by dependency.
        db: Active SQLAlchemy database session.

    Returns:
        BehaviorCreateOut containing the created behavior_id.

    Raises:
        HTTPException: 400 Bad Request if the user has no club or validation fails.
    """
    try:
        behavior = create_behavior(
            db=db,
            user_id=current_user.id,
            data=data,
        )
        return BehaviorCreateOut.model_validate(behavior)
    except (ValueError, BehaviorValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.put(
    "/{behavior_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def update_behavior_endpoint(
    behavior_id: int,
    data: BehaviorIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing custom behavior belonging to the authenticated user's club.

    Args:
        behavior_id: Identifier of the behavior to update.
        data: Request payload containing the updated name and Python source code.
        current_user: Currently authenticated user injected by dependency.
        db: Active SQLAlchemy database session.

    Returns:
        Empty 204 No Content response.

    Raises:
        HTTPException: 400 if validation fails, 403 if the behavior is default,
            or 404 if the behavior is not found.
    """
    try:
        update_behavior(
            db=db,
            user_id=current_user.id,
            behavior_id=behavior_id,
            data=data,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (ValueError, BehaviorValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except DefaultBehaviorModificationError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
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
