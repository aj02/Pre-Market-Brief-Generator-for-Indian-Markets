"""SQLModel tables and engine bootstrap."""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from sqlmodel import Field, Session, SQLModel, create_engine

from premarket.config import get_settings


class Brief(SQLModel, table=True):
    """One row per generated brief, keyed by target trading date."""

    model_config = {"protected_namespaces": ()}  # allow `model_used` field name

    id: int | None = Field(default=None, primary_key=True)
    target_date: str = Field(index=True, unique=True, max_length=10)
    generated_at: datetime
    model_used: str
    sections_json: str
    context_json: str


_settings = get_settings()
engine = create_engine(_settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    """Create tables on startup. Idempotent."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session
