"""Declarative model base; S1 adds the C.2 mappings."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base metadata for future literal C.2 model mappings."""
