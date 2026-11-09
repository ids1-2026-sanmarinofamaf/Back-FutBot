import asyncio

from fastapi import WebSocket
from time import monotonic

from app.game.active_matches import get_match
from app.game.models.match import MatchSnapshot, Match, PauseType
from app.game.penalties import PenaltyShootout
from app.game.penalty_session import PenaltySession
from app.game.types import Assignment, Substitution
from app.schemas.match_websocket import (
    MatchPlayerState,
    MatchPendingSubstitution,
    MatchStateMessage,
    BallState,
    MatchCoachChange,
    MatchCoachChangesMessage,
    MatchCoachSubstitution,
    MatchCoachSubstitutionsMessage,
    MatchPauseStartedMessage,
    MatchSubstitutionWindowClosedMessage,
    MatchPauseFinishedMessage,
    MatchTeamInfo,
    MatchPlayerInfo,
    MatchInfoMessage,
    PenaltyShootoutStartedMessage,
    PenaltyTurnStartedMessage,
    PenaltyResultMessage,
    PenaltyHistoryMessage,
    PenaltyShootoutFinishedMessage,
)


SEND_TIMEOUT_SECONDS = 1.0

class MatchConnectionManager:
    def __init__(self):
        # we relate the match_id with the connections it can have
        self.active_connections: dict[int, list[WebSocket]] = {}
        self.connection_clubs: dict[WebSocket, int | None] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}

    # since most WS operations use the network, we use await in case it takes a while
    async def connect(
        self,
        match_id: int,
        websocket: WebSocket,
        client_club_id: int | None = None,
    ) -> None:
        await websocket.accept()

        lock = self._send_locks.setdefault(websocket, asyncio.Lock())

        try:
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                async with lock:
                    self.active_connections.setdefault(match_id, []).append(websocket)
                    self.connection_clubs[websocket] = client_club_id

                    match = get_match(match_id)
                    if match is None:
                        return

                    match_info = build_match_info_message(
                        match,
                        my_club_id=client_club_id,
                    )
                    await websocket.send_json(match_info.model_dump(mode="json"))

                    initial_state = build_match_state_message(match.snapshot())
                    filtered_initial_state = filter_match_state_for_client(
                        initial_state,
                        client_club_id=client_club_id,
                        club_a_id=match.participation_a.club_id,
                        club_b_id=match.participation_b.club_id,
                        pending_a=match.participation_a.pending_substitution,
                        pending_b=match.participation_b.pending_substitution,
                    )
                    await websocket.send_json(
                        filtered_initial_state.model_dump(mode="json"),
                    )

                    session = match.penalty_session
                    if session is not None:
                        history_message = build_penalty_history_message(
                            session.shootout,
                        )

                        penalty_message = None

                        if match.winner_club_id is not None:
                            penalty_message = build_penalty_shootout_finished_message(
                                session.shootout,
                            )
                        elif session.accepting_choices:
                            penalty_message = build_penalty_turn_started_message(
                                session,
                            )

                        await websocket.send_json(
                            history_message.model_dump(mode="json"),
                        )

                        if penalty_message is not None:
                            await websocket.send_json(
                                penalty_message.model_dump(mode="json"),
                            )

        except (Exception, asyncio.CancelledError):
            self.disconnect(match_id, websocket)
            try:
                async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                    await websocket.close()
            except Exception:
                pass
            raise

    # given a WS connection and a match_id, we want to disconnect it from it
    def disconnect(self, match_id: int, websocket: WebSocket) -> None:
        self.connection_clubs.pop(websocket, None)
        self._send_locks.pop(websocket, None)

        # we get the ws connections from that match_id
        connections = self.active_connections.get(match_id, [])

        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)
        # if there are no connections related to that match, we delete the dictionary entry
        if not connections:
            self.active_connections.pop(match_id, None)

    async def _send_json(
        self,
        match_id: int,
        websocket: WebSocket,
        payload: dict,
    ) -> None:
        if websocket not in self.active_connections.get(match_id, []):
            return

        lock = self._send_locks.setdefault(websocket, asyncio.Lock())
        async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
            async with lock:
                if websocket in self.active_connections.get(match_id, []):
                    await websocket.send_json(payload)

    # we want to send message to everyone online
    async def broadcast(
        self,
        match_id: int,
        message: (
            MatchStateMessage
            | MatchCoachChangesMessage
            | MatchCoachSubstitutionsMessage
            | MatchPauseStartedMessage
            | MatchSubstitutionWindowClosedMessage
            | MatchPauseFinishedMessage
            | PenaltyShootoutStartedMessage
            | PenaltyTurnStartedMessage
            | PenaltyResultMessage
            | PenaltyShootoutFinishedMessage
        ),
    ) -> None:

        connections = (self.active_connections.get(match_id, [])).copy()

        disconnected: list[WebSocket] = []

        if isinstance(message, MatchStateMessage):
            match = get_match(match_id)
            club_a_id = match.participation_a.club_id if match is not None else None
            club_b_id = match.participation_b.club_id if match is not None else None
            pending_a = (
                match.participation_a.pending_substitution
                if match is not None
                else None
            )
            pending_b = (
                match.participation_b.pending_substitution
                if match is not None
                else None
            )

            for websocket in connections:
                client_club_id = self.connection_clubs.get(websocket)
                filtered_msg = filter_match_state_for_client(
                    message,
                    client_club_id=client_club_id,
                    club_a_id=club_a_id,
                    club_b_id=club_b_id,
                    pending_a=pending_a,
                    pending_b=pending_b,
                )
                try:
                    await self._send_json(
                        match_id,
                        websocket,
                        filtered_msg.model_dump(mode="json"),
                    )

                except Exception:
                    disconnected.append(websocket)
        elif isinstance(message, MatchCoachChangesMessage):
            # each club only learns what its own coach assigned
            for websocket in connections:
                client_club_id = self.connection_clubs.get(websocket)
                filtered_msg = filter_coach_changes_for_client(
                    message,
                    client_club_id=client_club_id,
                )

                if filtered_msg is None:
                    continue

                try:
                    await self._send_json(
                        match_id,
                        websocket,
                        filtered_msg.model_dump(mode="json"),
                    )
                except Exception:
                    disconnected.append(websocket)
        else:
            for websocket in connections:
                try:
                    await self._send_json(
                        match_id,
                        websocket,
                        message.model_dump(mode="json"),
                    )

                except Exception:
                    disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(match_id, websocket)

    async def close_match_connection(self, match_id: int) -> None:
        connections = self.active_connections.get(match_id, [])

        # clean the dictionary entry before closing the connections
        self.active_connections.pop(match_id, None)

        for websocket in connections:
            self.connection_clubs.pop(websocket, None)
            lock = self._send_locks.pop(websocket, asyncio.Lock())
            try:
                async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                    async with lock:
                        await websocket.close()

            except Exception:
                pass

# prepare the message that will be sent through the websocket
def build_match_state_message(
    snapshot: MatchSnapshot,
) -> MatchStateMessage:

    players: list[MatchPlayerState] = []

    for player in snapshot.players_a:
        players.append(
            MatchPlayerState(
                player_id=player.player_id,
                x=player.position[0],
                y=player.position[1],
                is_on_field=player.is_on_field,
                team="A",
                current_behavior_id=player.current_behavior_id,
                current_behavior_name=player.current_behavior_name,
            )
        )

    for player in snapshot.players_b:
        players.append(
            MatchPlayerState(
                player_id=player.player_id,
                x=player.position[0],
                y=player.position[1],
                is_on_field=player.is_on_field,
                team="B",
                current_behavior_id=player.current_behavior_id,
                current_behavior_name=player.current_behavior_name,
            )
        )

    return MatchStateMessage(
        event="estado_partido",

        actual_tic=snapshot.current_tick,
        total_tic=snapshot.duration_ticks,

        user1_goals=snapshot.score_a,
        user2_goals=snapshot.score_b,

        current_period=snapshot.current_period.value,
        is_paused=snapshot.is_paused,
        pause_type=snapshot.pause_type,
        substitution_window_open=snapshot.substitution_window_open,

        ball=BallState(
            x=snapshot.ball.position[0],
            y=snapshot.ball.position[1],
            speed_x=snapshot.ball.velocity[0],
            speed_y=snapshot.ball.velocity[1],
        ),
        players=players,
    )


# prepare the message with the coach assignments applied in a tick,
# from the result of match.apply_pending_behavior_changes()
def build_coach_changes_message(
    applied_assignments: dict[int, list[Assignment]],
    from_tic: int,
) -> MatchCoachChangesMessage:

    return MatchCoachChangesMessage(
        from_tic=from_tic,
        changes=[
            MatchCoachChange(
                club_id=club_id,
                player_id=player_id,
                behavior=behavior_name,
            )
            for club_id, assignments in applied_assignments.items()
            for player_id, behavior_name in assignments
        ],
    )


# prepare the message with the coach substitutions executed in a break,
# from the result of match.close_and_execute_substitutions()
def build_coach_substitutions_message(
    executed_substitutions: list[tuple[int, Substitution]],
) -> MatchCoachSubstitutionsMessage:

    return MatchCoachSubstitutionsMessage(
        changes=[
            MatchCoachSubstitution(
                club_id=club_id,
                player_out_id=substitution.player_out_id,
                player_in_id=substitution.player_in_id,
            )
            for club_id, substitution in executed_substitutions
        ],
    )


def filter_coach_changes_for_client(
    message: MatchCoachChangesMessage,
    client_club_id: int | None,
) -> MatchCoachChangesMessage | None:
    """
    Keep only the coach changes of the client's own club.

    Returns None when nothing is left (rival changes only, or a spectator),
    so the client does not receive an empty event.
    """
    if client_club_id is None:
        return None

    own_changes = [
        change
        for change in message.changes
        if change.club_id == client_club_id
    ]

    if not own_changes:
        return None

    return message.model_copy(update={"changes": own_changes})


def filter_match_state_for_client(
    message: MatchStateMessage,
    client_club_id: int | None,
    club_a_id: int | None,
    club_b_id: int | None,
    pending_a=None,
    pending_b=None,
) -> MatchStateMessage:
    """
    Oculta current_behavior_id y current_behavior_name de los jugadores rivales
    o de ambos equipos si el cliente es un espectador, e incluye únicamente la
    sustitución pendiente del propio club.
    """
    filtered_players: list[MatchPlayerState] = []

    for player in message.players:
        is_own = (
            client_club_id is not None
            and (
                (player.team == "A" and client_club_id == club_a_id)
                or (player.team == "B" and client_club_id == club_b_id)
            )
        )

        if is_own:
            filtered_players.append(player)
        else:
            filtered_players.append(
                player.model_copy(
                    update={
                        "current_behavior_id": None,
                        "current_behavior_name": None,
                    }
                )
            )

    own_pending = None
    if client_club_id is not None:
        if client_club_id == club_a_id and pending_a is not None:
            own_pending = MatchPendingSubstitution(
                player_out_id=pending_a.player_out_id,
                player_in_id=pending_a.player_in_id,
            )
        elif client_club_id == club_b_id and pending_b is not None:
            own_pending = MatchPendingSubstitution(
                player_out_id=pending_b.player_out_id,
                player_in_id=pending_b.player_in_id,
            )

    return message.model_copy(
        update={
            "players": filtered_players,
            "pending_substitution": own_pending,
        }
    )


def build_pause_started_message(
    pause_type: PauseType,
    duration: float,
    planning_duration: float,
) -> MatchPauseStartedMessage:
    return MatchPauseStartedMessage(
        pause_type=pause_type,
        duration=duration,
        planning_duration=planning_duration,
    )


def build_substitution_window_closed_message(
    pause_type: PauseType,
) -> MatchSubstitutionWindowClosedMessage:
    return MatchSubstitutionWindowClosedMessage(
        pause_type=pause_type,
    )


def build_pause_finished_message(
    pause_type: PauseType,
) -> MatchPauseFinishedMessage:
    return MatchPauseFinishedMessage(
        pause_type=pause_type,
    )

def build_match_info_message(
    match: Match,
    my_club_id: int | None = None,
) -> MatchInfoMessage:

    participation_a = match.participation_a
    participation_b = match.participation_b

    players: list[MatchPlayerInfo] = []

    for player in participation_a.players:
        players.append(
            MatchPlayerInfo(
                player_id=player.player_id,
                name=player.name,
                team="A",
                club_id=participation_a.club_id,
                shirt_number=player.shirt_number,
            )
        )

    for player in participation_b.players:
        players.append(
            MatchPlayerInfo(
                player_id=player.player_id,
                name=player.name,
                team="B",
                club_id=participation_b.club_id,
                shirt_number=player.shirt_number,
            )
        )

    return MatchInfoMessage(
        match_id=match.match_id,
        my_club_id=my_club_id,

        team_a=MatchTeamInfo(
            club_id=participation_a.club_id,
            club_name=participation_a.club_name,
            coach_behavior_name=participation_a.coach_behavior_name,
        ),

        team_b=MatchTeamInfo(
            club_id=participation_b.club_id,
            club_name=participation_b.club_name,
            coach_behavior_name=participation_b.coach_behavior_name,
        ),

        players=players,
        
    )


def build_penalty_shootout_started_message(
    duration: float,
)-> PenaltyShootoutStartedMessage:
    if duration < 0:
        raise ValueError("Invalid penalties duration")

    return PenaltyShootoutStartedMessage(
        duration=duration,
    )


def build_penalty_turn_started_message(
    session: PenaltySession,
) -> PenaltyTurnStartedMessage:
    if not session.accepting_choices:
        raise ValueError("Penalty turn is closed")

    if session.deadline is None:
        raise RuntimeError("Open penalty turn has no deadline")

    shootout = session.shootout
    kicker_index = shootout.turn // 2

    if shootout.turn % 2 == 0:
        club_id = shootout.club_a_id
        kicker = shootout.kickers_a[kicker_index]

    else:
        club_id = shootout.club_b_id
        kicker = shootout.kickers_b[kicker_index]

    return PenaltyTurnStartedMessage(
        turn=shootout.turn + 1,
        club_id=club_id,
        kicker=kicker,
        score_club_a=shootout.score_a,
        score_club_b=shootout.score_b,
        remaining_seconds=max(
            0.0,
            session.deadline - monotonic(),
        ),
    )


def build_penalty_result_message(
    result: dict,
    duration: float,
) -> PenaltyResultMessage:
    return PenaltyResultMessage(**result, duration=duration)


def build_penalty_history_message(
    shootout: PenaltyShootout,
) -> PenaltyHistoryMessage:
    return PenaltyHistoryMessage(
        results=[
            build_penalty_result_message(result, duration=0)
            for result in shootout.results
        ],
    )


def build_penalty_shootout_finished_message(
    shootout: PenaltyShootout,
) -> PenaltyShootoutFinishedMessage:
    if shootout.winner_club_id is None:
        raise ValueError("Penalty shootout has no winner yet")

    return PenaltyShootoutFinishedMessage(
        winner_club_id=shootout.winner_club_id,
        score_club_a=shootout.score_a,
        score_club_b=shootout.score_b,
    )


match_connection_manager = MatchConnectionManager()
