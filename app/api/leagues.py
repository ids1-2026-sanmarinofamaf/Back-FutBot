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
    join_league,
    InvalidLeaguePassword,
    LeagueFull,
    InvalidRoster,
    LeagueNotAvailable,
    AlreadyParticipating,
)
from app.schemas.league import LeagueJoin, LeagueJoinResponse

router = APIRouter(prefix="/leagues",tags=["Leagues"])


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


@router.post(
    "/{league_id}/users",
    response_model=LeagueJoinResponse,
    status_code=status.HTTP_200_OK,
)
def join(
    league_id: int,
    data: LeagueJoin,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        participation, roster = join_league(
            db=db,
            league_id=league_id,
            user_id=current_user.id,
            data=data,
        )

        return LeagueJoinResponse(
            league_id=league_id,
            club_id=participation.club_id,
            roster_id=roster.id,
        )

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except (
        InvalidLeaguePassword,
        LeagueFull
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    except (
        LeagueNotAvailable,
        AlreadyParticipating,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except InvalidRoster as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error