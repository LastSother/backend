import json, os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.sql import text
from .db import init_db, SessionLocal
from .models import NPC, Event, Message
from .chat_ws import manager
from .npc_manager import NPCManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

init_db()

async def broadcaster(topic, payload):
    await manager.broadcast(topic, {"type": topic, "data": payload})

npc_manager = NPCManager(broadcaster)

@app.on_event('startup')
async def startup():
    db = SessionLocal()
    try:
        # Миграция старых записей
        db.execute(text("UPDATE messages SET role = 'user' WHERE role = 'npc'"))
        db.commit()
        logger.info("Successfully migrated messages table")
    except Exception as e:
        logger.error(f"Failed to migrate messages table: {e}")
    finally:
        db.close()
    await npc_manager.start()

@app.on_event('shutdown')
def shutdown():
    npc_manager.stop()

@app.get('/')
@app.head('/')
async def root():
    return JSONResponse({"message": "Welcome to the backend"})

@app.get('/favicon.ico')
async def favicon():
    return FileResponse("static/favicon.ico") if os.path.exists("static/favicon.ico") else JSONResponse(status_code=204)

@app.get('/map')
def get_map():
    db = SessionLocal()
    try:
        npcs = db.query(NPC).all()
        out = [{"id": n.id, "name": n.name, "x": n.x, "y": n.y, "profession": n.profession, "state": n.state} for n in npcs]  # Добавил state
        return out
    finally:
        db.close()

@app.get('/news')
def get_news():
    db = SessionLocal()
    try:
        evs = db.query(Event).order_by(Event.id.desc()).limit(50).all()
        out = [{"title": e.title, "content": e.content, "ts": e.ts} for e in evs]
        return out
    finally:
        db.close()

@app.get('/chat_history/{npc_id}')
def get_chat_history(npc_id: int):
    db = SessionLocal()
    try:
        hist = db.query(Message).filter(Message.npc_id == npc_id).order_by(Message.id).all()
        return [{"role": m.role, "content": m.content} for m in hist]
    finally:
        db.close()

@app.websocket('/ws/{topic}')
async def websocket_endpoint(websocket: WebSocket, topic: str):
    await manager.connect(topic, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {}
            if topic.startswith('npc_') and msg.get('action') == 'message':
                npc_id = int(topic.split('_', 1)[1])
                text = msg.get('text', '')
                db = SessionLocal()
                try:
                    npc = db.query(NPC).get(npc_id)
                    if not npc:
                        await manager.send_personal(websocket, {"type": "error", "data": "NPC not found"})
                        continue
                    system = f"Ты {npc.name}, {npc.personality}. Отвечай коротко и в характере. Учитывай отношения и погоду."
                    hist = db.query(Message).filter(Message.npc_id == npc_id).order_by(Message.id.desc()).limit(10).all()
                    history = [{'role': 'user' if m.role == 'npc' else m.role, 'content': m.content} for m in reversed(hist)]
                    logger.debug(f"WebSocket history for NPC {npc_id}: {history}")
                    db.add(Message(npc_id=npc_id, role='user', content=f"Player: {text}"))
                    db.commit()
                    from .ai import generate_reply
                    reply = await generate_reply(system, history, text)
                    db.add(Message(npc_id=npc_id, role='user', content=f"NPC_{npc.name}: {reply}"))
                    db.commit()
                    await manager.broadcast(topic, {"type": "chat", "data": {"npc_id": npc_id, "from": "npc", "text": reply}})
                finally:
                    db.close()
            elif topic.startswith('npc_') and msg.get('action') == 'command':
                npc_id = int(topic.split('_', 1)[1])
                command = msg.get('text', '')
                db = SessionLocal()
                try:
                    npc = db.query(NPC).get(npc_id)
                    if not npc:
                        await manager.send_personal(websocket, {"type": "error", "data": "NPC not found"})
                        continue
                    system = f"Ты {npc.name}. Выполни команду: {command}. Учитывай личность и состояние."
                    history = []
                    reply = await generate_reply(system, history, command)
                    # Обработка команды, напр. если "go to shop" - move
                    if 'go to' in command.lower():
                        loc_name = command.split('to')[-1].strip()
                        loc = db.query(Location).filter_by(name=loc_name).first()
                        if loc:
                            npc.x = random.uniform(loc.x_min, loc.x_max)
                            npc.y = random.uniform(loc.y_min, loc.y_max)
                            npc.state['location'] = loc_name
                            db.commit()
                            await broadcaster('map_update', {"id": npc.id, "x": npc.x, "y": npc.y, "location": loc_name})
                    db.add(Message(npc_id=npc_id, role='user', content=f"Command: {reply}"))
                    db.commit()
                    await manager.broadcast(topic, {"type": "command", "data": {"npc_id": npc_id, "reply": reply}})
                finally:
                    db.close()
            else:
                await manager.send_personal(websocket, {"type": "echo", "data": msg})
    except WebSocketDisconnect:
        manager.disconnect(topic, websocket)