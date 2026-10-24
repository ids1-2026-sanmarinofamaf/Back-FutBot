from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Path,
    Body,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.match import ChangePlayerBehaviorRequest
from app.services.match_service import change_player_behavior


router = APIRouter(
    prefix="/live_match",
    tags=["Live Match"],
)


@router.put(
    "/{lmatch_id}/me/{player_id}/behavior",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_player_behavior(
    lmatch_id: int = Path(gt=0),
    player_id: int = Path(gt=0),
    data: ChangePlayerBehaviorRequest = Body(),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        change_player_behavior(
            db=db,
            user_id=current_user.id,
            match_id=lmatch_id,
            player_id=player_id,
            behavior_id=data.behavior_id,
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error)
        ) from error

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from error