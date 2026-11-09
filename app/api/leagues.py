import logging
import asyncio

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
    cancel_league,
    LeagueForbidden,
    InvalidLeagueState,
    InsufficientLeagueParticipants,
    build_league_state,
    get_league_detail,
    get_my_league_ids,
    update_league_roster,
    get_league_roster,
)
from app.services.league_runner import start_league_runner

from app.schemas.league import (
    LeagueCreate,
    LeagueJoin,
    LeagueJoinResponse,
    LeagueUpdate,
    LeagueStartedEvent,
    LeagueDetail,
    MyLeaguesResponse
)
from app.schemas.roster import RosterCreate, RosterDetail
from app.schemas.league_websocket import LeagueCancelledEvent

SEND_TIMEOUT_SECONDS = 5


router = APIRouter(prefix="/leagues",tags=["Leagues"])
logger = logging.getLogger(__name__)


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


@router.delete(
    "/{league_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel(
    league_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        await run_in_threadpool(
            cancel_league,
            db=db,
            league_id=league_id,
            user_id=current_user.id,
        )

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except LeagueForbidden as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    except LeagueAlreadyStarted as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    # the cancellation is persisted, a notification failure must not turn it into an error
    try:
        try:
            await league_connection_manager.broadcast(
                league_id,
                LeagueCancelledEvent(league_id=league_id),
            )
        finally:
            await league_connection_manager.close_lobby(
                league_id,
                reason="League cancelled",
            )

        await session_websocket_service.broadcast_leagues(db)

    except Exception:
        logger.exception(
            "Failed to notify clients about league %s cancellation",
            league_id,
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
        await run_in_threadpool(
            start_league,
            db=db,
            league_id=league_id,
            user_id=current_user.id,
            requested_state=data.state,
        )

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except LeagueForbidden as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    except (
        LeagueAlreadyStarted,
        InvalidLeagueState,
        InsufficientLeagueParticipants,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    # League start and fixture are confirmed
    try:
        try:

            league = league_repository.get_by_id(db, league_id)
            fixture, standings = build_league_state(db, league)

            start_league_event = LeagueStartedEvent(
                league_id=league_id,
                fixture=fixture,
                standings=standings,
            )

            payload = session_websocket_service.build_leagues_payload(db)
        
        finally:
            db.close()

        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            await league_connection_manager.broadcast(
                league_id,
                start_league_event,
            )

            await session_websocket_service.broadcast_leagues_payload(payload)

    except Exception:
        logger.exception(
            "Failed to notify clients about league %s startup",
            league_id,
        )

    finally:
        start_league_runner(league_id)


@router.get("/me", response_model=MyLeaguesResponse)
async def get_my_leagues(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    league_ids = await run_in_threadpool(
        get_my_league_ids,
        db,
        current_user.id,
    )

    return MyLeaguesResponse(league_ids=league_ids)


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


@router.put(
    "/{league_id}/users/me/roster",
    status_code=status.HTTP_200_OK,
)
async def update_my_league_roster(
    league_id: int,
    data: RosterCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        await run_in_threadpool(
            update_league_roster,
            db=db,
            league_id=league_id,
            user_id=current_user.id,
            data=data,
        )

        return {"message": "Roster updated successfully"}

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except LeagueForbidden as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    except InvalidLeagueState as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except InvalidRoster as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

# obtain the respective league particiátion roster
@router.get(
    "/{league_id}/users/me/roster",
    response_model=RosterDetail,
    status_code=status.HTTP_200_OK,
)
async def get_my_league_roster(
    league_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return await run_in_threadpool(
            get_league_roster,
            db=db,
            league_id=league_id,
            user_id=current_user.id,
        )

    except LeagueNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except LeagueForbidden as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
