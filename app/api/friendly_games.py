from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.friendly_game import (FriendlyGameCreate,FriendlyGameCreateResponse,FriendlyGameJoin,FriendlyGameJoinResponse,)

from app.services.friendly_game_service import (
    create_friendly_game,
    join_friendly_game,
    FriendlyGameNotFound,
    FriendlyGameNotAvailable,
    FriendlyGameFull,
    AlreadyParticipating,
    InvalidRoster,
)
from app.api.deps import get_current_user


router = APIRouter(
    prefix="/friendly_games",
    tags=["Friendly Games"]
)


@router.post("",
    response_model=FriendlyGameCreateResponse,
    status_code=status.HTTP_201_CREATED
)
def create(
    data: FriendlyGameCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        friendly_game, roster = create_friendly_game(
            db=db,
            user_id=current_user.id,
            data=data
        )

        return FriendlyGameCreateResponse(
            friendly_game_id=friendly_game.id,
            roster_id=roster.id
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

@router.post(
    "/{friendly_game_id}/users",
    response_model=FriendlyGameJoinResponse,
    status_code=status.HTTP_201_CREATED
)
def join(
    friendly_game_id: int,
    data: FriendlyGameJoin,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    try:
        participation, roster = join_friendly_game(
            db=db,
            friendly_game_id=friendly_game_id,
            user_id=current_user.id,
            data=data,
        )
        # verificar si agregar participation o no
        return FriendlyGameJoinResponse(
            friendly_game_id=friendly_game_id,
            participation_id=participation.id,
            roster_id=roster.id,
        )

    except FriendlyGameNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    except (
        FriendlyGameNotAvailable,
        FriendlyGameFull,
        AlreadyParticipating,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    except InvalidRoster as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )