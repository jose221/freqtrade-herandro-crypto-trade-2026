"""
Interfaces (abstracciones) para la capa de base de datos.
Principio SOLID: Dependency Inversion - depender de abstracciones, no de implementaciones.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session


class IConnectionProvider(ABC):
    """Interfaz para proveedores de conexión a base de datos."""

    @abstractmethod
    def get_engine(self):
        """Retorna el engine de SQLAlchemy."""
        ...

    @abstractmethod
    def dispose(self) -> None:
        """Libera todos los recursos del pool de conexiones."""
        ...


class ISessionManager(ABC):
    """Interfaz para gestión de sesiones de base de datos."""

    @abstractmethod
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Context manager que provee una sesión con manejo automático de transacciones."""
        ...

    @abstractmethod
    def get_scoped_session(self):
        """Retorna la sesión con scope para uso en FastAPI/threads."""
        ...

    @abstractmethod
    def remove_session(self) -> None:
        """Elimina la sesión del scope actual (evita fugas de conexiones)."""
        ...


class IRepository(ABC):
    """Interfaz base para repositorios de datos."""

    @abstractmethod
    def get_by_id(self, entity_id: int): ...

    @abstractmethod
    def get_all(self): ...

    @abstractmethod
    def save(self, entity) -> None: ...

    @abstractmethod
    def delete(self, entity_id: int) -> None: ...
