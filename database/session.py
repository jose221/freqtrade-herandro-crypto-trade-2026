"""
Gestor de sesiones de base de datos para Freqtrade + PostgreSQL.
Principios SOLID:
  - Single Responsibility: solo gestiona el ciclo de vida de sesiones.
  - Liskov Substitution: implementa ISessionManager completamente.

Prevención de fugas de conexiones:
  - session_scope() have commit/rollback/close automáticamente.
  - remove_session() libera la sesión del scope actual.
  - Uso de scoped_session con scopefunc por hilo/request.
"""

import logging
import threading
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Final

from sqlalchemy.orm import Session, scoped_session, sessionmaker

from database.interfaces import IConnectionProvider, ISessionManager


logger = logging.getLogger(__name__)

REQUEST_ID_CTX_KEY: Final[str] = "request_id"
_request_id_ctx_var: ContextVar[str | None] = ContextVar(REQUEST_ID_CTX_KEY, default=None)


def get_request_or_thread_id() -> str | None:
    """
    Retorna el ID de request (FastAPI) o el ID del hilo actual.
    Usado como scopefunc para scoped_session.
    """
    request_id = _request_id_ctx_var.get()
    if request_id is None:
        request_id = str(threading.current_thread().ident)
    return request_id


class DatabaseSessionManager(ISessionManager):
    """
    Gestiona sesiones SQLAlchemy con scope por hilo/request.
    Garantiza que cada hilo/request tenga su propia sesión y que
    las conexiones sean devueltas al pool al finalizar.
    """

    def __init__(self, connection_provider: IConnectionProvider) -> None:
        """
        :param connection_provider: Proveedor de conexión (IConnectionProvider).
        """
        engine = connection_provider.get_engine()
        self._session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        self._scoped_session: scoped_session[Session] = scoped_session(
            self._session_factory,
            scopefunc=get_request_or_thread_id,
        )
        logger.info("DatabaseSessionManager: sesiones configuradas.")

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Context manager que provee una sesión con manejo automático de transacciones.
        Have commit si no hay excepciones, rollback si las hay, y siempre cierra la sesión.

        Uso:
            with session_manager.session_scope() as session:
                session.add(entity)
        """
        session: Session = self._scoped_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Error en transacción, se realizó rollback.")
            raise
        finally:
            # Devuelve la conexión al pool y elimina la sesión del scope
            self._scoped_session.remove()

    def get_scoped_session(self) -> scoped_session[Session]:
        """
        Retorna la scoped_session para uso directo en modelos (Trade.session, etc.).
        Compatible con el patrón existente de Freqtrade.
        """
        return self._scoped_session

    def remove_session(self) -> None:
        """
        Elimina la sesión del scope actual.
        Debe llamarse al final de cada request HTTP para evitar fugas de conexiones.
        """
        self._scoped_session.remove()
        logger.debug("DatabaseSessionManager: sesión del scope actual eliminada.")
