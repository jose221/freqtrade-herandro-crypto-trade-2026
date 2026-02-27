"""
Configuración de la base de datos PostgreSQL leída desde variables de entorno.
Principio SOLID: Single Responsibility - solo gestiona la configuración.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """
    Configuración immutable de la base de datos.
    Los valores se leen de variables de entorno con fallback a defaults seguros.
    """

    db_url: str
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    echo: bool

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Crea la configuración leyendo variables de entorno.
        Lanza ValueError si FREQTRADE_DB_URL no está definida.
        """
        db_url = os.environ.get("FREQTRADE_DB_URL", "")
        if not db_url:
            raise ValueError(
                "La variable de entorno FREQTRADE_DB_URL no está definida. "
                "Ejemplo: postgresql+psycopg2://user:pass@localhost:5432/freqtrade_db"
            )
        return cls(
            db_url=db_url,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
            pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "1800")),
            echo=os.environ.get("DB_ECHO", "false").lower() == "true",
        )

    @classmethod
    def from_url(cls, db_url: str, **kwargs) -> "DatabaseConfig":
        """Crea la configuración a partir de una URL explícita."""
        return cls(
            db_url=db_url,
            pool_size=kwargs.get("pool_size", 10),
            max_overflow=kwargs.get("max_overflow", 20),
            pool_timeout=kwargs.get("pool_timeout", 30),
            pool_recycle=kwargs.get("pool_recycle", 1800),
            echo=kwargs.get("echo", False),
        )
