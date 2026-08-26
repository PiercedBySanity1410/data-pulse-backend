import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config

def create_db_engine():
    db_url = Config.DATABASE_URL or os.getenv("DATABASE_URL", "sqlite:///./datapulse_local.db")
    
    # Standardize postgres dialect for SQLAlchemy
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    connect_args = {}
    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False

    try:
        if "sqlite" in db_url:
            eng = create_engine(db_url, connect_args=connect_args)
        else:
            eng = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args=connect_args
            )
        return eng
    except Exception as e:
        print(f"[Database Warning] Failed to initialize engine for {db_url}: {e}. Falling back to SQLite.")
        return create_engine("sqlite:///./datapulse_local.db", connect_args={"check_same_thread": False})

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db(target_engine=None):
    use_engine = target_engine or engine
    Base.metadata.create_all(bind=use_engine)