"""資料庫連線（SQLite）。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_conn, _record):
    # SQLite 預設不檢查外鍵，這裡打開
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
