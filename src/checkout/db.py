"""Database engine, session factory and the FastAPI session dependency."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from checkout.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,  # transparently replace connections MySQL has dropped
    pool_recycle=3600,  # recycle before MySQL's wait_timeout kicks in
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_session() -> Iterator[Session]:
    """One session per request; closed automatically afterwards."""
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
