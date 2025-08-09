from sqlalchemy import Column, Integer, String, Float, JSON, Text
from .db import Base

class NPC(Base):
    __tablename__ = 'npcs'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    profession = Column(String)
    personality = Column(Text)
    state = Column(JSON, default={"mood": "neutral", "money": 100, "location": "home", "relations": {}, "business": None})  # Добавил relations, business
    x = Column(Float, default=0.0)
    y = Column(Float, default=0.0)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, index=True)
    npc_id = Column(Integer, index=True)
    role = Column(String)
    content = Column(Text)

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    ts = Column(String)

class Location(Base):
    __tablename__ = 'locations'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    x_min = Column(Float)
    x_max = Column(Float)
    y_min = Column(Float)
    y_max = Column(Float)

class Weather(Base):  # Добавил погоду
    __tablename__ = 'weather'
    id = Column(Integer, primary_key=True, index=True)
    current = Column(String, default="sunny")  # sunny, rainy, stormy