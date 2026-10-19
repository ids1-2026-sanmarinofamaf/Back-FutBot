from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.game.active_matches import get_match
from app.repositories import club_repository
from app.schemas.match import SubstitutionRequest

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

    club = club_repository.get_by_user_id(db,current_user.id)

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