from fastapi import WebSocket

from app.game.models.match import MatchSnapshot
from app.game.types import Assignment, Substitution
from app.schemas.match_websocket import (
    MatchPlayerState,
    MatchStateMessage,
    BallState,
    MatchCoachChange,
    MatchCoachChangesMessage,
    MatchCoachSubstitution,
    MatchCoachSubstitutionsMessage,
    MatchPauseStartedMessage,
    MatchSubstitutionWindowClosedMessage,
    MatchPauseFinishedMessage,
)


class MatchConnectionManager:
    def __init__(self):
        # we relate the match_id with the connections it can have
        self.active_connections: dict[int, list[WebSocket]] = {}

    # since most WS operations use the network, we use await in case it takes a while
    async def connect(self, match_id: int, websocket: WebSocket) -> None:
        # accept de ws conection
        await websocket.accept()

        # if there was no connection to that match, we create the empty ws list
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []

        # We save the connection in the respective match_id
        self.active_connections[match_id].append(websocket)

    # given a WS connection and a match_id, we want to disconnect it from it
    def disconnect(self, match_id: int, websocket: WebSocket) -> None:
        # we get the ws connections from that match_id
        connections = self.active_connections.get(match_id, [])

        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)
        # if there are no connections related to that match, we delete the dictionary entry
        if not connections:
            self.active_connections.pop(match_id, None)

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
    ),
    ) -> None:

        connections = (self.active_connections.get(match_id, [])).copy()

        disconnected = []
        # sent the status for everyone
        for websocket in connections:
            try:
                await websocket.send_json(message.model_dump())
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(match_id, websocket)

    async def close_match_connection(self, match_id: int) -> None:
        connections = self.active_connections.get(match_id, [])

        # clean the dictionary entry before closing the connections
        self.active_connections.pop(match_id, None)

        for websocket in connections:
            try:    
                await websocket.close()

            except Exception:
                pass

# prepare the messahe that will be sended by through the websocket
def build_match_state_message(
    snapshot: MatchSnapshot,
) -> MatchStateMessage:

    players = []

    for player in snapshot.players_a:
        players.append(
            MatchPlayerState(
                player_id=player.player_id,
                x=player.position[0],
                y=player.position[1],
                is_on_field=player.is_on_field,
                team="A",
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
            )
        )

    return MatchStateMessage(
        event="estado_partido",

        actual_tic=snapshot.current_tick,
        total_tic=snapshot.duration_ticks,

        user1_goals=snapshot.score_a,
        user2_goals=snapshot.score_b,

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


def build_pause_started_message(
    pause_type: str,
    duration: float,
    planning_duration: float,
) -> MatchPauseStartedMessage:
    return MatchPauseStartedMessage(
        pause_type=pause_type,
        duration=duration,
        planning_duration=planning_duration,
    )


def build_substitution_window_closed_message(
    pause_type: str,
) -> MatchSubstitutionWindowClosedMessage:
    return MatchSubstitutionWindowClosedMessage(
        pause_type=pause_type,
    )


def build_pause_finished_message(
    pause_type: str,
) -> MatchPauseFinishedMessage:
    return MatchPauseFinishedMessage(
        pause_type=pause_type,
    )



match_connection_manager = MatchConnectionManager()
