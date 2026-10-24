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
    ClubNotFound,
    create_league
)
from app.schemas.league import LeagueCreate


router = APIRouter(prefix="/leagues",tags=["Leagues"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create(
    data: LeagueCreate,
    db: Session = Depends(get_db),
    current_user= Depends(get_current_user), 
):
    try: 
        league = create_league(
            db,
            data,
            current_user.id
        )
        return {"id_liga": league.id}
    # here we use the exception classes
    except ClubNotFound as error:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    # invalid roster (players or behaviors)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

@router.delete(
    "/{league_id}/users/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
def leave(
    league_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        leave_league(
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