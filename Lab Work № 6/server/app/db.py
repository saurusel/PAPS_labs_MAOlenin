from __future__ import annotations

import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://merch:merch@localhost:5432/merchdb")

engine_kwargs: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

ENGINE = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db_and_seed() -> None:
    from app.models import Base, UserPoints

    for attempt in range(1, 31):
        try:
            Base.metadata.create_all(ENGINE)
            break
        except Exception:
            if attempt == 30:
                raise
            time.sleep(1)

    with SessionLocal() as db:
        try:
            for user_id, balance in {"u1": 5000, "u2": 2000}.items():
                if not db.get(UserPoints, user_id):
                    db.add(UserPoints(user_id=user_id, balance=balance))
            db.commit()
        except Exception:
            db.rollback()
            raise
