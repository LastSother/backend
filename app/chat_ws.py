from fastapi import WebSocket
import json
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.topics: Dict[str, List[WebSocket]] = {}

    async def connect(self, topic: str, ws: WebSocket):
        await ws.accept()
        self.topics.setdefault(topic, []).append(ws)

    def disconnect(self, topic: str, ws: WebSocket):
        if topic in self.topics and ws in self.topics[topic]:
            self.topics[topic].remove(ws)

    async def send_personal(self, ws: WebSocket, message: dict):
        await ws.send_text(json.dumps(message, ensure_ascii=False))

    async def broadcast(self, topic: str, message: dict):
        if topic not in self.topics:
            return
        for ws in list(self.topics[topic]):
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                pass

manager = ConnectionManager()