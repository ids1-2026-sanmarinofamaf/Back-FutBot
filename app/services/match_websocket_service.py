from fastapi import WebSocket

from app.game.models.match import MatchSnapshot


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

        if connections is []:
            return

        if websocket in connections:
            connections.remove(websocket)

        # if there are no connections related to that match, we delete the dictionary entry
        if not connections:
            del self.active_connections[match_id]

    # we want to send message to everyone online
    async def broadcast(self, match_id: int, message: dict) -> None:
    
        connections = self.active_connections.get(match_id,[])

        # we sent the status to everyone
        for websocket in connections:
            await websocket.send_json(message)

    async def close_match_connection(self, match_id: int) -> None:
        connections = self.active_connections.get(match_id, [])

        for websocket in connections:
            await websocket.close()
        # after closing the connections, we clean the dictionary entry for that match
        self.active_connections.pop(match_id, None)


# we transform the game state into a json to send over ws
def build_match_state_message(snapshot: MatchSnapshot) -> dict:

    # we get all the starting players, since they are the ones shown on the field
    players = []

    for player in snapshot.players_a:
        if player.is_on_field:
            players.append({
                "player_id": player.player_id,
                "x": player.position[0],
                "y": player.position[1],
            })

    for player in snapshot.players_b:
        if player.is_on_field:
            players.append({
                "player_id": player.player_id,
                "x": player.position[0],
                "y": player.position[1],
            })

    # we name the event we're going to send, and fill in the rest of the match information.
    return {
        "event": "estado_partido",

        "actual_tic": snapshot.current_tick,
        "total_tic": snapshot.duration_ticks,

        "user1_goals": snapshot.score_a,
        "user2_goals": snapshot.score_b,

        "ball": {
            "x": snapshot.ball.position[0],
            "y": snapshot.ball.position[1],
            "speed_x": snapshot.ball.velocity[0],
            "speed_y": snapshot.ball.velocity[1],
        },

        "players": players,
    }

match_connection_manager = MatchConnectionManager()