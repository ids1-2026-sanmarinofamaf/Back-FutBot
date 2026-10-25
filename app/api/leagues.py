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
    start_league,
    LeagueForbidden,
    InvalidLeagueState,
    InsufficientLeagueParticipants,
)

from app.schemas.league import LeagueUpdate

from fastapi.concurrency import run_in_threadpool
from app.services import session_websocket_service


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


@router.patch(
    "/{league_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def start(
    league_id: int,
    data: LeagueUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        # avoid blocking the event loop with synchronous database operations
        await run_in_threadpool(
            start_league,
            db=db,
            league_id=league_id,
            user_id=current_user.id,
            requested_state=data.state,
        )

        # send the broadcast start league  in ws session
        await session_websocket_service.broadcast_leagues(db)

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    except LeagueForbidden as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )

    except (
        LeagueAlreadyStarted,
        InvalidLeagueState,
        InsufficientLeagueParticipants,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
