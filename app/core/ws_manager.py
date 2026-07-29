from fastapi import WebSocket


class ConnectionManager:


    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, merchant_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(merchant_id, []).append(websocket)

    def disconnect(self, merchant_id: int, websocket: WebSocket):
        connections = self.active_connections.get(merchant_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and merchant_id in self.active_connections:
            del self.active_connections[merchant_id]

    async def send_to_merchant(self, merchant_id: int, message: dict):

        connections = self.active_connections.get(merchant_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(merchant_id, ws)


manager = ConnectionManager()