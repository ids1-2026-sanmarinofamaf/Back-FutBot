from fastapi import (
    APIRouter,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from app.database import SessionLocal

from app.models.friendly_game import (FriendlyGameState)

from app.repositories import (club_repository,friendly_game_repository)

from app.services import auth_service

from app.services.friendly_game_websocket_service import (
    friendly_game_connection_manager,
    build_friendly_game_lobby_state,
)

router = APIRouter(
    tags=["Friendly Games WebSocket"]
)


async def reject_websocket(
    websocket: WebSocket,
    code: int,
    reason: str,
) -> None:
    """
    Aceptamos y cerramos inmediatamente para que el cliente
    reciba un close frame WebSocket con nuestro código 44xx.
    """
    await websocket.accept()

    await websocket.close(
        code=code,
        reason=reason,
    )


@router.websocket("/ws/friendly_game/{friendly_game_id}")
async def friendly_game_websocket(
    websocket: WebSocket,
    friendly_game_id: int,
    token: str | None = Query(default=None),
):
    # authentication with jwt
    if token is None:
        await reject_websocket(
            websocket,
            code=4401,
            reason="Authentication token required",
        )
        return

    with SessionLocal() as db:

        try:
            user = auth_service.get_user_from_token(db,token)

        except auth_service.InvalidToken:
            await reject_websocket(
                websocket,
                code=4401,
                reason="Invalid or expired token",
            )
            return

        # validate the frindly_game existence
        friendly_game = friendly_game_repository.get_by_id(
            db=db,
            friendly_game_id=friendly_game_id,
        )

        if friendly_game is None:
            await reject_websocket(
                websocket,
                code=4404,
                reason="Friendly game not found",
            )
            return

        club = club_repository.get_by_user_id(db,user.id,)

        # clun must be participating 
        participation = (
            friendly_game_repository
            .get_participation_by_club(
                db=db,
                friendly_game_id=friendly_game_id,
                club_id=club.id,
            )
        )

        if participation is None:
            await reject_websocket(
                websocket,
                code=4403,
                reason=("Club doesnt participate in this friendly game")
            )
            return

        # friendly game state must be: POR_COMENZAR
        if (friendly_game.state != FriendlyGameState.POR_COMENZAR):
            await reject_websocket(
                websocket,
                code=4409,
                reason="Friendly game lobby is no longer available",
            )
            return

        # build the message
        initial_state = (
            build_friendly_game_lobby_state(
                friendly_game=friendly_game,
                match_id=None,
            )
        )

    # connect
    await friendly_game_connection_manager.connect(friendly_game_id,websocket)

    try:

        # send the state
        await friendly_game_connection_manager.send_state(
            websocket,
            initial_state,
        )

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        friendly_game_connection_manager.disconnect(
            friendly_game_id,
            websocket,
        )