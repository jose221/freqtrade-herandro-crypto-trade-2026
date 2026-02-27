"""
PostgreSQL connection provider for Freqtrade.
SOLID Principles:
  - Single Responsibility: only manages connection/pool.
  - Open/Closed: extensible via IConnectionProvider.
  - Dependency Inversion: implements IConnectionProvider.

Connection leak prevention optimizations:
  - pool_pre_ping: validates connections before use.
  - pool_recycle: recycles old connections.
  - pool_size + max_overflow: limits active connections.
  - pool_timeout: prevents infinite waits.
"""

import logging
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool, QueuePool

from database.interfaces import IConnectionProvider


logger = logging.getLogger(__name__)


class DatabaseConnection(IConnectionProvider):
    """
    Manages SQLAlchemy engine with PostgreSQL and a connection pool
    configured to prevent leaks and maximize security.
    """

    def __init__(
        self,
        db_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        echo: bool = False,
        use_null_pool: bool = False,
    ) -> None:
        """
        :param db_url: PostgreSQL connection URL.
                       Example: postgresql+psycopg2://user:pass@host:5432/dbname
        :param pool_size: Number of permanent connections in the pool.
        :param max_overflow: Extra connections allowed above pool_size.
        :param pool_timeout: Maximum seconds waiting for a connection from pool.
        :param pool_recycle: Seconds before recycling a connection (avoids server timeouts).
        :param echo: If True, logs all SQL statements (development only).
        :param use_null_pool: If True, uses NullPool (no pool, useful for workers/scripts).
        """
        self._db_url = db_url
        self._engine: Engine | None = None

        kwargs: dict[str, Any] = {
            "future": True,
            "echo": echo,
            "pool_pre_ping": True,  # Validates connection before use (prevents dead connections)
        }

        if use_null_pool:
            # NullPool: each operation opens and closes its own connection. Ideal for scripts.
            kwargs["poolclass"] = NullPool
        else:
            kwargs.update(
                {
                    "poolclass": QueuePool,
                    "pool_size": pool_size,
                    "max_overflow": max_overflow,
                    "pool_timeout": pool_timeout,
                    "pool_recycle": pool_recycle,
                }
            )

        self._engine = create_engine(db_url, **kwargs)
        self._register_pool_events()
        logger.info("DatabaseConnection: PostgreSQL engine created successfully.")

    def _register_pool_events(self) -> None:
        """Registers pool events for monitoring and logging."""

        @event.listens_for(self._engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            logger.debug("Pool: new physical connection opened.")

        @event.listens_for(self._engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Pool: connection delivered to requesting thread.")

        @event.listens_for(self._engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            logger.debug("Pool: connection returned to the pool.")

    def get_engine(self) -> Engine:
        """Returns the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("The engine has not been initialized.")
        return self._engine

    def health_check(self) -> bool:
        """Verifies that the database is accessible."""
        if self._engine is None:
            raise RuntimeError("The engine has not been initialized.")
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.error("Database health check failed: %s", exc)
            return False

    def dispose(self) -> None:
        """
        Releases all connections in the pool.
        Should be called when shutting down the application to prevent leaks.
        """
        if self._engine:
            self._engine.dispose()
            logger.info("DatabaseConnection: connection pool released.")
