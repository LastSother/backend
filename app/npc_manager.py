import asyncio, random
from datetime import datetime
import logging
from .db import SessionLocal
from .models import NPC, Message, Event, Location, Weather
from .ai import generate_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_NPC_PROFILES = [
    {"name": "Анна", "profession": "Бариста", "personality": "дружелюбная, болтливая, оптимист"},
    {"name": "Пётр", "profession": "Полицейский", "personality": "строгий, справедливый, серьёзный"},
    {"name": "Оля", "profession": "Журналист", "personality": "любопытная, амбициозная, чуть драматична"},
    {"name": "Игорь", "profession": "Таксист", "personality": "шутник, практичный, наблюдательный"},
    {"name": "Мария", "profession": "Учитель", "personality": "терпеливая, заботливая"},
    {"name": "Сергей", "profession": "Программист", "personality": "скромный, аналитичный, любит кофе"},
    {"name": "Лена", "profession": "Врач", "personality": "серьёзная, эмпатичная"},
    {"name": "Дмитрий", "profession": "Механик", "personality": "рукастый, немного ворчлив"},
    {"name": "Ирина", "profession": "Художник", "personality": "романтичная, креативная"},
    {"name": "Николай", "profession": "Продавец", "personality": "прозорливый, хитрый"},
    {"name": "Виктория", "profession": "Студентка", "personality": "энергичная, соцсети-ориентированная"},
    {"name": "Алексей", "profession": "Пекарь", "personality": "теплый, гостеприимный"},
    {"name": "Галина", "profession": "Пенсионерка", "personality": "ворчливая, мудрая"},
]

class NPCManager:
    def __init__(self, broadcaster):
        self.broadcaster = broadcaster
        self.tasks = []
        self.seeded = False

    def seed(self):
        db = SessionLocal()
        try:
            existing = db.query(NPC).count()
            if existing >= len(DEFAULT_NPC_PROFILES):
                return
            npcs = []
            for p in DEFAULT_NPC_PROFILES:
                relations = {other['name']: random.choice(['friend', 'neutral', 'enemy']) for other in DEFAULT_NPC_PROFILES if other['name'] != p['name']}
                npc = NPC(
                    name=p['name'],
                    profession=p['profession'],
                    personality=p['personality'],
                    state={"mood": "neutral", "money": 100, "location": "home", "relations": relations, "business": None},
                    x=random.random() * 800,
                    y=random.random() * 400
                )
                npcs.append(npc)
            db.add_all(npcs)
            db.commit()
        finally:
            db.close()
        self.seeded = True

    async def npc_loop(self, npc):
        while True:
            await asyncio.sleep(random.randint(10, 30))  # Замедление перемещений
            db = SessionLocal()
            try:
                weather = db.query(Weather).first().current
                actions = ['move', 'chat', 'work', 'shop', 'business', 'disaster']  # Добавил business, disaster
                if weather == 'rainy':
                    actions = ['move'] if random.random() > 0.5 else actions  # Чаще дома
                action = random.choice(actions)
                if action == 'move':
                    locations = db.query(Location).all()
                    target_loc = random.choice(locations)
                    if weather == 'sunny' and target_loc.name == 'park':
                        target_loc = db.query(Location).filter_by(name='park').first()  # Предпочтение парку в солнце
                    npc.x = random.uniform(target_loc.x_min, target_loc.x_max)
                    npc.y = random.uniform(target_loc.y_min, target_loc.y_max)
                    npc.state['location'] = target_loc.name
                    db.commit()
                    await self.broadcaster('map_update', {"id": npc.id, "x": npc.x, "y": npc.y, "location": target_loc.name})
                elif action == 'chat':
                    others = db.query(NPC).filter(NPC.id != npc.id).all()
                    if not others:
                        return
                    other = random.choice(others)
                    relation = npc.state['relations'].get(other.name, 'neutral')
                    system = f"Ты {npc.name}, {npc.personality}. Отношение к {other.name}: {relation}. Общайся коротко."
                    history = []
                    reply = await generate_reply(system, history, f"Привет, {other.name}! Как дела?")
                    db.add(Message(npc_id=npc.id, role='user', content=f"NPC_{npc.name}: {reply}"))
                    db.commit()
                    ev = Event(
                        title=f"Разговор: {npc.name} и {other.name}",
                        content=reply,
                        ts=str(datetime.utcnow())
                    )
                    db.add(ev)
                    db.commit()
                    await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
                    # Обновление отношений
                    if 'злость' in reply.lower():
                        npc.state['relations'][other.name] = 'enemy'
                    elif 'дружба' in reply.lower():
                        npc.state['relations'][other.name] = 'friend'
                    db.commit()
                elif action == 'work' and npc.state.get('location') == 'work':
                    s = npc.state
                    s['money'] += random.randint(10, 20)
                    npc.state = s
                    db.commit()
                    await self.broadcaster('state_update', {"id": npc.id, "state": npc.state})
                elif action == 'shop' and npc.state.get('location') == 'shop':
                    s = npc.state
                    spent = random.randint(5, 15)
                    s['money'] = max(0, s['money'] - spent)
                    npc.state = s
                    db.commit()
                    ev = Event(
                        title=f"Покупка: {npc.name}",
                        content=f"{npc.name} купил вещи на {spent} монет.",
                        ts=str(datetime.utcnow())
                    )
                    db.add(ev)
                    db.commit()
                    await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
                elif action == 'business':
                    if not npc.state['business']:
                        system = f"Ты {npc.name}, {npc.profession}. Придумай бизнес-идею."
                        idea = await generate_reply(system, [], "Предложи идею бизнеса.")
                        npc.state['business'] = idea
                        db.commit()
                        ev = Event(title=f"Новый бизнес: {npc.name}", content=idea, ts=str(datetime.utcnow()))
                        db.add(ev)
                        db.commit()
                        await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
                    else:
                        npc.state['money'] += random.randint(5, 10)  # Доход от бизнеса
                        db.commit()
                elif action == 'disaster':
                    if random.random() < 0.1:  # Редко
                        disaster = random.choice(['fire', 'theft'])
                        system = f"Генерируй событие катастрофы для {npc.name}."
                        desc = await generate_reply(system, [], f"Опиши {disaster}.")
                        ev = Event(title=f"Катастрофа: {disaster} у {npc.name}", content=desc, ts=str(datetime.utcnow()))
                        db.add(ev)
                        db.commit()
                        await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
                        npc.state['money'] -= random.randint(20, 50)  # Убыток
                        db.commit()
            finally:
                db.close()

    async def weather_loop(self):
        while True:
            await asyncio.sleep(300)  # Каждые 5 мин
            db = SessionLocal()
            try:
                weather = db.query(Weather).first()
                weather.current = random.choice(['sunny', 'rainy', 'stormy'])
                db.commit()
                ev = Event(title="Погода изменилась", content=f"Теперь {weather.current}.", ts=str(datetime.utcnow()))
                db.add(ev)
                db.commit()
                await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
            finally:
                db.close()

    async def election_loop(self):
        while True:
            await asyncio.sleep(300)  # Каждые 5 мин
            db = SessionLocal()
            try:
                npcs = db.query(NPC).all()
                votes = {npc.name: 0 for npc in npcs}
                for voter in npcs:
                    candidate = random.choice(npcs).name
                    votes[candidate] += 1
                winner = max(votes, key=votes.get)
                ev = Event(title="Выборы мэра", content=f"Новый мэр: {winner} с {votes[winner]} голосами.", ts=str(datetime.utcnow()))
                db.add(ev)
                db.commit()
                await self.broadcaster('news', {"title": ev.title, "content": ev.content, "ts": ev.ts})
                # Игрок может влиять через команды
            finally:
                db.close()

    async def start(self):
        self.seed()
        db = SessionLocal()
        try:
            npcs = db.query(NPC).all()
            for npc in npcs:
                task = asyncio.create_task(self.npc_loop(npc))
                self.tasks.append(task)
            self.tasks.append(asyncio.create_task(self.weather_loop()))
            self.tasks.append(asyncio.create_task(self.election_loop()))
        finally:
            db.close()

    def stop(self):
        for t in self.tasks:
            t.cancel()