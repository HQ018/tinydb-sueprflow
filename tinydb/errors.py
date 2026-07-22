class TinyDBError(Exception):
    """Base class for user-visible TinyDB errors."""


class DatabaseError(TinyDBError):
    """Raised for public API misuse or invalid database lifecycle operations."""


class ParseError(TinyDBError):
    """Raised when SQL text cannot be parsed."""


class ExecutionError(TinyDBError):
    """Raised when a valid request cannot be executed."""


class ConstraintError(TinyDBError):
    """Raised when schema or row constraints are violated."""


class ConcurrencyError(TinyDBError):
    """Raised when TinyDB cannot safely acquire a concurrency lock."""


class StorageError(TinyDBError):
    """Raised when database file storage cannot be read or written safely."""


class TransactionError(TinyDBError):
    """Raised when transaction state or recovery fails."""
