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

    with SessionLocal() as db:
        try:
            user = auth_service.get_user_from_token(db, token)

        except auth_service.InvalidToken:
            await reject_websocket(
                websocket,
                4401,
                "Invalid or expired token",
            )
            return

        # check whether the league exists
        league = league_repository.get_by_id(
            db=db,
            league_id=league_id,
        )

        if league is None:
            await reject_websocket(
                websocket,
                4404,
                "League not found",
            )
            return

        # get the authenticated user's club
        club = club_repository.get_by_user_id(
            db=db,
            user_id=user.id,
        )

        if club is None:
            await reject_websocket(
                websocket,
                4403,
                "User has no club",
            )
            return

        # check whether the club participates in the league
        participation = (
            league_participation_repository
            .get_participation_by_club_and_league(
                db=db,
                league_id=league_id,
                club_id=club.id,
            )
        )

        if participation is None:
            await reject_websocket(
                websocket,
                4403,
                "Club does not participate in this league",
            )
            return

        # build the initial lobby state
        initial_state = build_league_lobby_state(league)
        user_id = user.id

    # accept and register the WebSocket connection
    await league_connection_manager.connect(
        league_id,
        user_id,
        websocket,
    )

    try:
        # when a user connect to a league websocket, we send the currente league state
        await league_connection_manager.send_state(websocket,initial_state)

        # keep the connection open
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        # remove the connection when it closes
        league_connection_manager.disconnect(
            league_id,
            user_id,
            websocket,
        )
