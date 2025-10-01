from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    params: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(String, ForeignKey("jobs.id"), nullable=True)
    url: Mapped[str] = mapped_column(String)
    org: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    emails: Mapped[str | None] = mapped_column(String, nullable=True)
    phones: Mapped[str | None] = mapped_column(String, nullable=True)
    socials: Mapped[str | None] = mapped_column(String, nullable=True)
    ok: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

def init_db():
    if engine is None:
        return
    Base.metadata.create_all(engine)
