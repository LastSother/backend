from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

BASE_DIR = os.path.dirname(__file__)
DB_FILE = os.path.join(BASE_DIR, 'city.db')
SQLITE_URL = os.environ.get('SQLITE_URL', f"sqlite:///{DB_FILE}")

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(models.Location).first():
            locations = [
                models.Location(name="home", x_min=0, x_max=200, y_min=0, y_max=200),
                models.Location(name="shop", x_min=200, x_max=400, y_min=200, y_max=400),
                models.Location(name="work", x_min=400, x_max=600, y_min=0, y_max=200),
                models.Location(name="park", x_min=600, x_max=800, y_min=200, y_max=400),
                models.Location(name="mayor_office", x_min=0, x_max=200, y_min=200, y_max=400),  # Добавил для выборов
            ]
            db.add_all(locations)
            db.commit()
        if not db.query(models.Weather).first():
            db.add(models.Weather(current="sunny"))
            db.commit()
    finally:
        db.close()