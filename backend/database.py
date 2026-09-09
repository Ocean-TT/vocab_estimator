from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import DATABASE_URL

# SQLite + check_same_thread=False 是 FastAPI 的标配写法
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖注入：每个请求拿一个 session，用完关"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
