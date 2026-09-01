import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Support Managed PostgreSQL (Supabase, Neon, Render Postgres) or Fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render / Postgres fix for SQLAlchemy dialect
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    # Local development SQLite
    SQLALCHEMY_DATABASE_URL = "sqlite:///./orderstream.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
