"""
Type helpers for SQLAlchemy/SQLModel compatibility with type checkers.

SQLModel fields are declared with Python types (e.g., `name: str`) but at the
class level they're actually InstrumentedAttribute descriptors with SQLAlchemy
column methods like .desc(), .in_(), .ilike(), etc.

Type checkers (mypy, ty) see them as plain Python types and report errors when
column methods are called. This module provides helpers to bridge that gap.
"""

from typing import TYPE_CHECKING, Any, TypeVar, Tuple, List, Optional, overload, Sequence
from datetime import datetime, timezone

if TYPE_CHECKING:
    from sqlalchemy.orm.attributes import InstrumentedAttribute

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")


def col(attr: T) -> "InstrumentedAttribute[T]":
    """
    Type helper for SQLAlchemy column operations in queries.

    Wraps a SQLModel field to tell the type checker it's an InstrumentedAttribute
    with column methods available (.desc(), .in_(), .ilike(), .is_(), etc.).

    At runtime this is a no-op - it just returns the input unchanged.

    Usage:
        from app.core.typing import col

        # Before (type error):
        select(Card).order_by(Card.name.desc())

        # After (type-safe):
        select(Card).order_by(col(Card.name).desc())
    """
    return attr  # type: ignore[return-value]


def result_scalar(result: Any) -> Any:
    """
    Type helper for SQLAlchemy Result scalar access.

    Helps with accessing .scalar(), .one(), .first() results.
    """
    return result


def utc_now() -> datetime:
    """
    Get current UTC time (timezone-aware).

    Replaces deprecated datetime.utcnow() which returns naive datetime.
    Use as default_factory in SQLModel fields.

    Usage:
        created_at: datetime = Field(default_factory=utc_now)
    """
    return datetime.now(timezone.utc)


def result_row(result: Any, index: int = 0) -> Any:
    """
    Type helper for accessing Result row by index.

    Usage:
        row = result_row(session.exec(query).first())
        value = row[0]  # No type error
    """
    return result


def ensure_list(value: Optional[List[T]]) -> List[T]:
    """
    Ensure a value is a list, returning empty list if None.

    Usage:
        items: Optional[List[Item]] = None
        for item in ensure_list(items):  # No type error
            process(item)
    """
    return value if value is not None else []


def ensure_tuple(result: Any) -> Tuple[Any, ...]:
    """
    Type helper for SQLAlchemy row results that are tuples.

    Usage:
        row = ensure_tuple(session.exec(query).first())
        if row:
            col1, col2 = row[0], row[1]
    """
    return result if result is not None else ()


def safe_getattr(obj: Any, name: str, default: T = None) -> T:  # type: ignore[assignment]
    """
    Type-safe getattr for dynamically accessed attributes.

    Usage:
        # Instead of: result.rowcount (type error)
        count = safe_getattr(result, 'rowcount', 0)
    """
    return getattr(obj, name, default)


@overload
def unpack_row(row: None) -> None: ...
@overload
def unpack_row(row: Tuple[T1]) -> Tuple[T1]: ...
@overload
def unpack_row(row: Tuple[T1, T2]) -> Tuple[T1, T2]: ...
@overload
def unpack_row(row: Tuple[T1, T2, T3]) -> Tuple[T1, T2, T3]: ...
@overload
def unpack_row(row: Any) -> Tuple[Any, ...]: ...

def unpack_row(row: Any) -> Any:
    """
    Type helper for unpacking SQLAlchemy result rows.

    Usage:
        row = unpack_row(session.exec(query).first())
        if row:
            total_sales, total_volume = row
    """
    return row


def seq(items: Any) -> Sequence[Any]:
    """
    Type helper for sequences (lists, tuples) in SQLAlchemy contexts.

    Usage:
        card_ids = [1, 2, 3]
        query.where(col(Card.id).in_(seq(card_ids)))
    """
    return items


def ensure_int(value: Optional[int], default: int = 0) -> int:
    """
    Convert Optional[int] to int for schema construction.

    SQLModel primary keys are Optional[int] because they're auto-generated,
    but when constructing Pydantic schemas from DB records, we know they exist.

    Usage:
        # Instead of: CardOut(id=card.id)  # type error
        CardOut(id=ensure_int(card.id))  # type-safe
    """
    return value if value is not None else default


def ensure_str(value: Optional[str], default: str = "") -> str:
    """
    Convert Optional[str] to str for schema construction.

    Usage:
        name = ensure_str(record.name)
    """
    return value if value is not None else default


def ensure_float(value: Optional[float], default: float = 0.0) -> float:
    """
    Convert Optional[float] to float for schema construction.

    Usage:
        price = ensure_float(record.price)
    """
    return value if value is not None else default


# Re-export common type patterns
__all__ = [
    "col",
    "result_scalar",
    "result_row",
    "ensure_list",
    "ensure_tuple",
    "safe_getattr",
    "unpack_row",
    "seq",
    "ensure_int",
    "ensure_str",
    "ensure_float",
]
