from sqlalchemy.orm import Session

from fastapi import (
    APIRouter,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from app.database import SessionLocal

from app.repositories import (
    league_repository,
    league_participation_repository,
    club_repository,
)

from app.services import auth_service

from app.services.league_websocket_service import (
    league_connection_manager,
    build_league_lobby_state,
)
from app.services.league_service import (
    LeagueNotFound,
    get_league_detail,
)
from app.models.user import User
from app.models.league import League

from app.schemas.league_websocket import LeagueStateEvent


router = APIRouter(tags=["League WebSocket"])


async def reject_websocket(
    websocket: WebSocket,
    code: int,
    reason: str,
) -> None:
    # reject a connection with a specific websocket close code
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


@router.websocket("/ws/league/{league_id}")
async def league_websocket(
    websocket: WebSocket,
    league_id: int,
    token: str | None = Query(default=None),
):
    # validate the authentication token
    if token is None:
        await reject_websocket(
            websocket,
            4401,
            "Authentication token required",
        )
        return

    try:
        with SessionLocal() as db:
            user, league = _validate_league_access(
                db,
                league_id,
                token
            )

            user_id = user.id
            
    except auth_service.InvalidToken:
        await reject_websocket(
            websocket,
            4401,
            "Invalid or expired token",
        )
        return

    except LeagueNotFound:
        await reject_websocket(
            websocket,
            4404,
            "League not found",
        )
        return

    except PermissionError as error:
        await reject_websocket(
            websocket,
            4403,
            str(error),
        )
        return

    try:
        await league_connection_manager.connect(
            league_id,
            user_id,
            websocket,
            initializing=True,
        )

        with SessionLocal() as db:
            _, league = _validate_league_access(
                db,
                league_id,
                token,
            )

            lobby_state = build_league_lobby_state(league)
            league_state = LeagueStateEvent(
                data=get_league_detail(db, league_id),
            )

        await league_connection_manager.send_initial_states(
            websocket,
            lobby_state,
            league_state,
        )

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    except auth_service.InvalidToken:
        await league_connection_manager.close_connection(
            league_id,
            user_id,
            websocket,
            code=4401,
            reason="Invalid or expired token",
        )

    except LeagueNotFound:
        await league_connection_manager.close_connection(
            league_id,
            user_id,
            websocket,
            code=4404,
            reason="League not found",
        )

    except PermissionError as error:
        await league_connection_manager.close_connection(
            league_id,
            user_id,
            websocket,
            code=4403,
            reason=str(error),
        )

    except Exception:
        await league_connection_manager.close_connection(
            league_id,
            user_id,
            websocket,
            code=1011,
            reason="Unable to initialize or maintain league connection",
        )
        raise

    finally:
        league_connection_manager.disconnect(
            league_id,
            user_id,
            websocket,
        )


def _validate_league_access(
    db: Session,
    league_id: int,
    token: str,
) -> tuple[User, League]:
    user = auth_service.get_user_from_token(db, token)

    league = league_repository.get_by_id(
        db=db,
        league_id=league_id,
    )

    if league is None:
        raise LeagueNotFound("League not found")

    club = club_repository.get_by_user_id(
        db=db,
        user_id=user.id,
    )

    if club is None:
        raise PermissionError("User has no club")

    participation = (
        league_participation_repository
        .get_participation_by_club_and_league(
            db=db,
            league_id=league_id,
            club_id=club.id,
        )
    )

    if participation is None:
        raise PermissionError("Club does not participate in this league")

    return user, league