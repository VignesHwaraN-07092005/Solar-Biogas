import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import settings

# Configure SQLite connect_args if using SQLite
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            res = conn.exec_driver_sql("PRAGMA table_info(forecast_results);").fetchall()
            existing_cols = [r[1] for r in res]
            if existing_cols:
                if "domain_valid" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE forecast_results ADD COLUMN domain_valid BOOLEAN DEFAULT 1;")
                if "domain_note" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE forecast_results ADD COLUMN domain_note VARCHAR(256);")
                conn.commit()
