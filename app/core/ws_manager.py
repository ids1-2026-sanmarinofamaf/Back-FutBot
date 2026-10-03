"""Registro de las conexiones WebSocket abiertas en ws/sessions."""

from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        # user_id -> conexiones abiertas de ese usuario (puede tener varias pestañas)
        self.active: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        connections = self.active.get(user_id)
        if connections is None:
            return  # ya se habia sacado (por ejemplo, desde broadcast)
        connections.discard(websocket)
        if not connections:
            del self.active[user_id]

    async def broadcast(self, message: str):
        # Copia de las conexiones: mientras se espera cada send_text otro
        # usuario puede conectarse o desconectarse y modificar self.active
        targets = [
            (user_id, conn)
            for user_id, connections in self.active.items()
            for conn in connections
        ]
        for user_id, conn in targets:
            try:
                await conn.send_text(message)
            except Exception:
                # Conexion caida: se saca sin afectar a los demas usuarios
                self.disconnect(user_id, conn)


manager = ConnectionManager()
