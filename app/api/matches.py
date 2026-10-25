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
from app.game.active_matches import get_match
from app.repositories import club_repository
from app.schemas.match import (
    ChangePlayerBehaviorRequest,
    SubstitutionRequest,
)
from app.services.match_service import change_player_behavior


router = APIRouter(tags=["Matches"])


@router.put(
    "/live_match/{match_id}/me/{player_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def plan_substitution(
    match_id: int,
    player_id: int,
    data: SubstitutionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    match = get_match(match_id)

    if match is None:
        raise HTTPException(404, "Match not found")

    club = club_repository.get_by_user_id(db, current_user.id)

    if club is None:
        raise HTTPException(403, "User has no club")

    try:
        match.plan_substitution(
            club_id=club.id,
            player_out_id=player_id,
            player_in_id=data.new_player,
        )

    except PermissionError as error:
        raise HTTPException(403, str(error))

    except ValueError as error:
        raise HTTPException(409, str(error))

    return None


@router.put(
    "/live_match/{lmatch_id}/me/{player_id}/behavior",
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
            detail=str(error),
        ) from error

    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error