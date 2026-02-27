"""
Bootstrap de la capa de base de datos PostgreSQL para Freqtrade.
Punto de entrada único para inicializar conexión, sesiones y repositorios.

Principio SOLID: Dependency Inversion - los consumidores reciben dependencias
inyectadas desde aquí, sin conocer las implementaciones concretas.

Uso típico en Freqtrade (reemplaza init_db de freqtrade/persistence/models.py):

    from database.bootstrap import init_postgres, get_repositories

    init_postgres()
    repos = get_repositories()
    trades = repos.trades.get_open_trades(bot_id=1)
"""

import logging
from dataclasses import dataclass

from database.config import DatabaseConfig
from database.connection import DatabaseConnection
from database.interfaces import IConnectionProvider, ISessionManager
from database.models import Base
from database.repositories import (
    AuditLogRepository,
    BotConfigRepository,
    BotRepository,
    ExchangeCredentialRepository,
    NotificationSettingRepository,
    OrderRepository,
    PairLockRepository,
    StrategyRepository,
    TradeRepository,
    UserRepository,
    UserSessionRepository,
)
from database.session import DatabaseSessionManager


logger = logging.getLogger(__name__)

# Instancias globales (singleton por proceso)
_connection: IConnectionProvider | None = None
_session_manager: ISessionManager | None = None


@dataclass
class Repositories:
    """Contenedor de todos los repositorios disponibles."""

    users: UserRepository
    user_sessions: UserSessionRepository
    bots: BotRepository
    bot_configs: BotConfigRepository
    exchange_credentials: ExchangeCredentialRepository
    trades: TradeRepository
    orders: OrderRepository
    pair_locks: PairLockRepository
    strategies: StrategyRepository
    notification_settings: NotificationSettingRepository
    audit_logs: AuditLogRepository


def init_postgres(config: DatabaseConfig | None = None) -> ISessionManager:
    """
    Inicializa la conexión PostgreSQL y crea todas las tablas si no existen.

    :param config: DatabaseConfig. Si es None, lee de variables de entorno.
    :return: ISessionManager listo para usar.

    Ejemplo:
        # Desde variables de entorno (.env):
        init_postgres()

        # Con URL explícita:
        cfg = DatabaseConfig.from_url("postgresql+psycopg2://user:pass@localhost/db")
        init_postgres(cfg)
    """
    global _connection, _session_manager

    if config is None:
        config = DatabaseConfig.from_env()

    _connection = DatabaseConnection(
        db_url=config.db_url,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_recycle=config.pool_recycle,
        echo=config.echo,
    )

    # Verificar conectividad antes de continuar
    if not _connection.health_check():
        raise RuntimeError(
            "No se pudo conectar a PostgreSQL. "
            "Verifica que el servidor esté corriendo y que FREQTRADE_DB_URL sea correcta."
        )

    _session_manager = DatabaseSessionManager(_connection)

    # Crear tablas si no existen (equivalente a ModelBase.metadata.create_all)
    engine = _connection.get_engine()
    Base.metadata.create_all(engine)
    logger.info("PostgreSQL: todas las tablas verificadas/creadas correctamente.")

    return _session_manager


def get_session_manager() -> ISessionManager:
    """Retorna el session manager global. Lanza RuntimeError si no fue inicializado."""
    if _session_manager is None:
        raise RuntimeError(
            "La base de datos no ha sido inicializada. "
            "Llama a init_postgres() antes de usar get_session_manager()."
        )
    return _session_manager


def get_repositories() -> Repositories:
    """
    Retorna un contenedor con todos los repositorios listos para usar.
    Require que init_postgres() haya sido llamado previamente.
    """
    sm = get_session_manager()
    return Repositories(
        users=UserRepository(sm),
        user_sessions=UserSessionRepository(sm),
        bots=BotRepository(sm),
        bot_configs=BotConfigRepository(sm),
        exchange_credentials=ExchangeCredentialRepository(sm),
        trades=TradeRepository(sm),
        orders=OrderRepository(sm),
        pair_locks=PairLockRepository(sm),
        strategies=StrategyRepository(sm),
        notification_settings=NotificationSettingRepository(sm),
        audit_logs=AuditLogRepository(sm),
    )


def shutdown_postgres() -> None:
    """
    Libera todas las conexiones del pool.
    Llamar al apagar la aplicación para evitar fugas de conexiones.
    """
    global _connection, _session_manager
    if _connection:
        _connection.dispose()
        _connection = None
        _session_manager = None
        logger.info("PostgreSQL: conexiones liberadas correctamente.")
