from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user

from app.services.league_service import (
    leave_league,
    LeagueNotFound,
    LeagueCreatorCannotLeave,
    LeagueAlreadyStarted,
    LeagueParticipationNotFound,
)


router = APIRouter(prefix="/leagues",tags=["Leagues"])


@router.delete(
    "/{league_id}/users/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave(
    league_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        await leave_league(
            db=db,
            league_id=league_id,
            user_id=current_user.id,
        )
    # here we use the exception classes
    except LeagueCreatorCannotLeave as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )

    except LeagueAlreadyStarted as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    except (
        LeagueNotFound,
        LeagueParticipationNotFound,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )