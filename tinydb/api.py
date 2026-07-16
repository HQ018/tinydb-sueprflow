from pathlib import Path
from threading import RLock

from tinydb.errors import DatabaseError, ExecutionError
from tinydb.executor import Executor
from tinydb.sql import parse_sql
from tinydb.storage import StorageManager
from tinydb.transaction import TransactionManager


class Database:
    def __init__(self, path: str | Path, lock_timeout: float | None = None):
        self._instance_lock = RLock()
        self.path = Path(path)
        self._closed = False
        self._storage = StorageManager(self.path)
        self._transactions = TransactionManager(self._storage, lock_timeout=lock_timeout)
        self._executor = Executor(self._storage, self._transactions)

    def execute(self, sql: str, parameters: object = None):
        with self._instance_lock:
            if self._closed:
                raise DatabaseError("database is closed")
            if not isinstance(sql, str):
                raise DatabaseError("SQL text is required")
            if parameters is not None:
                raise ExecutionError("SQL parameters are not implemented yet")
            return self._executor.execute(parse_sql(sql))

    def close(self) -> None:
        with self._instance_lock:
            if not self._closed:
                self._transactions.close()
                self._storage.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
