
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from app.services.league_websocket_service import league_connection_manager
from fastapi.concurrency import run_in_threadpool

from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.services import session_websocket_service
from app.repositories import league_repository
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
    ClubNotFound,
    create_league,
    start_league,
    LeagueForbidden,
    InvalidLeagueState,
    InsufficientLeagueParticipants,
    build_league_state,
    get_league_detail,
)
from app.schemas.league import LeagueCreate, LeagueJoin, LeagueJoinResponse, LeagueUpdate, LeagueStartedEvent, LeagueDetail

router = APIRouter(prefix="/leagues",tags=["Leagues"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    data: LeagueCreate,
    db: Session = Depends(get_db),
    current_user= Depends(get_current_user),
):
    try:
        league = await run_in_threadpool(
            create_league,
            db,
            data,
            current_user.id
        )
        await session_websocket_service.broadcast_leagues(db)
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

        await session_websocket_service.broadcast_leagues(db)

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
async def join(
    league_id: int,
    data: LeagueJoin,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        participation, roster = await join_league(
            db=db,
            league_id=league_id,
            user_id=current_user.id,
            data=data,
        )

        await session_websocket_service.broadcast_leagues(db)

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

        # league expires after commit so we call back
        league  = league_repository.get_by_id(db, league_id)

        fixture, standings = build_league_state(db, league)
        
        # Event create
        start_league_event = LeagueStartedEvent(
            league_id=league_id,
            fixture=fixture,
            standings=standings,
        )
        await league_connection_manager.broadcast(league_id, start_league_event)

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


@router.get(
    "/{league_id}",
    response_model=LeagueDetail,
    status_code=status.HTTP_200_OK,
)
async def get_by_id(
    league_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        # fixture and standings come filled when the league is INICIADA
        return await run_in_threadpool(
            get_league_detail,
            db=db,
            league_id=league_id,
        )

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
