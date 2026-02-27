"""
Capa de consulta de base de datos (Query Layer / Repositories).
Principios SOLID:
  - Single Responsibility: cada repositorio gestiona una sola entidad.
  - Open/Closed: nuevos repositorios extienden BaseRepository sin modificarlo.
  - Liskov Substitution: todos implementan IRepository.
  - Interface Segregation: interfaces específicas por dominio.
  - Dependency Inversion: dependen de ISessionManager, no de implementaciones concretas.
"""

import logging
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.interfaces import IRepository, ISessionManager
from database.models import (
    AuditLog,
    Bot,
    BotConfig,
    ExchangeCredential,
    NotificationSetting,
    Order,
    PairLock,
    Strategy,
    Trade,
    User,
    UserSession,
)


logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Repositorio base genérico
# ---------------------------------------------------------------------------


class BaseRepository(IRepository, Generic[T]):
    """
    Repositorio base con operaciones CRUD genéricas.
    Todas las operaciones reciben una sesión explícita para permitir
    transacciones que abarquen múltiples repositorios.
    """

    def __init__(self, model_class: type[T], session_manager: ISessionManager) -> None:
        self._model = model_class
        self._session_manager = session_manager

    def _session(self) -> Session:
        return self._session_manager.get_scoped_session()()

    def get_by_id(self, entity_id: int) -> T | None:
        session = self._session()
        return session.get(self._model, entity_id)

    def get_all(self) -> list[T]:
        session = self._session()
        return list(session.execute(select(self._model)).scalars().all())

    def save(self, entity: T) -> None:
        session = self._session()
        session.add(entity)
        session.flush()

    def delete(self, entity_id: int) -> None:
        session = self._session()
        entity = session.get(self._model, entity_id)
        if entity:
            session.delete(entity)
            session.flush()


# ---------------------------------------------------------------------------
# Repositorio de Usuarios
# ---------------------------------------------------------------------------


class UserRepository(BaseRepository[User]):
    """Consultas específicas para la entidad User."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(User, session_manager)

    def get_by_username(self, username: str) -> User | None:
        session = self._session()
        return session.execute(select(User).where(User.username == username)).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        session = self._session()
        return session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def get_active_users(self) -> list[User]:
        session = self._session()
        return list(session.execute(select(User).where(User.is_active)).scalars().all())


# ---------------------------------------------------------------------------
# Repositorio de Sesiones de Usuario
# ---------------------------------------------------------------------------


class UserSessionRepository(BaseRepository[UserSession]):
    """Consultas específicas para sesiones JWT."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(UserSession, session_manager)

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        session = self._session()
        return session.execute(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        ).scalar_one_or_none()

    def get_active_sessions_for_user(self, user_id: int) -> list[UserSession]:
        session = self._session()
        now = datetime.utcnow()
        return list(
            session.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.expires_at > now,
                )
            )
            .scalars()
            .all()
        )

    def delete_expired_sessions(self) -> int:
        session = self._session()
        now = datetime.utcnow()
        expired = (
            session.execute(select(UserSession).where(UserSession.expires_at <= now))
            .scalars()
            .all()
        )
        count = len(expired)
        for s in expired:
            session.delete(s)
        session.flush()
        return count


# ---------------------------------------------------------------------------
# Repositorio de Bots
# ---------------------------------------------------------------------------


class BotRepository(BaseRepository[Bot]):
    """Consultas específicas para la entidad Bot."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(Bot, session_manager)

    def get_bots_by_owner(self, owner_id: int) -> list[Bot]:
        session = self._session()
        return list(session.execute(select(Bot).where(Bot.owner_id == owner_id)).scalars().all())

    def get_running_bots(self) -> list[Bot]:
        from database.models import BotStatus

        session = self._session()
        return list(
            session.execute(select(Bot).where(Bot.status == BotStatus.RUNNING)).scalars().all()
        )

    def get_by_owner_and_name(self, owner_id: int, name: str) -> Bot | None:
        session = self._session()
        return session.execute(
            select(Bot).where(Bot.owner_id == owner_id, Bot.name == name)
        ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Repositorio de Configuración de Bot
# ---------------------------------------------------------------------------


class BotConfigRepository(BaseRepository[BotConfig]):
    """Consultas específicas para configuraciones de bot."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(BotConfig, session_manager)

    def get_by_bot_id(self, bot_id: int) -> BotConfig | None:
        session = self._session()
        return session.execute(
            select(BotConfig).where(BotConfig.bot_id == bot_id)
        ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Repositorio de Credenciales de Exchange
# ---------------------------------------------------------------------------


class ExchangeCredentialRepository(BaseRepository[ExchangeCredential]):
    """Consultas para credenciales de exchange."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(ExchangeCredential, session_manager)

    def get_by_bot_id(self, bot_id: int) -> ExchangeCredential | None:
        session = self._session()
        return session.execute(
            select(ExchangeCredential).where(ExchangeCredential.bot_id == bot_id)
        ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Repositorio de Trades
# ---------------------------------------------------------------------------


class TradeRepository(BaseRepository[Trade]):
    """Consultas específicas para trades."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(Trade, session_manager)

    def get_open_trades(self, bot_id: int) -> list[Trade]:
        session = self._session()
        return list(
            session.execute(select(Trade).where(Trade.bot_id == bot_id, Trade.is_open))
            .scalars()
            .all()
        )

    def get_closed_trades(self, bot_id: int) -> list[Trade]:
        session = self._session()
        return list(
            session.execute(select(Trade).where(Trade.bot_id == bot_id, ~Trade.is_open))
            .scalars()
            .all()
        )

    def get_trades_by_pair(self, bot_id: int, pair: str) -> list[Trade]:
        session = self._session()
        return list(
            session.execute(select(Trade).where(Trade.bot_id == bot_id, Trade.pair == pair))
            .scalars()
            .all()
        )

    def count_open_trades(self, bot_id: int) -> int:
        session = self._session()
        from sqlalchemy import func

        result = session.execute(
            select(func.count()).select_from(Trade).where(Trade.bot_id == bot_id, Trade.is_open)
        ).scalar()
        return result or 0

    def get_trades_in_date_range(self, bot_id: int, start: datetime, end: datetime) -> list[Trade]:
        session = self._session()
        return list(
            session.execute(
                select(Trade).where(
                    Trade.bot_id == bot_id,
                    Trade.open_date >= start,
                    Trade.open_date <= end,
                )
            )
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# Repositorio de Órdenes
# ---------------------------------------------------------------------------


class OrderRepository(BaseRepository[Order]):
    """Consultas específicas para órdenes."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(Order, session_manager)

    def get_orders_by_trade(self, trade_id: int) -> list[Order]:
        session = self._session()
        return list(
            session.execute(select(Order).where(Order.trade_id == trade_id)).scalars().all()
        )

    def get_open_orders_by_trade(self, trade_id: int) -> list[Order]:
        session = self._session()
        return list(
            session.execute(select(Order).where(Order.trade_id == trade_id, Order.ft_is_open))
            .scalars()
            .all()
        )

    def get_by_order_id(self, order_id: str, pair: str) -> Order | None:
        session = self._session()
        return session.execute(
            select(Order).where(Order.order_id == order_id, Order.ft_pair == pair)
        ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Repositorio de PairLocks
# ---------------------------------------------------------------------------


class PairLockRepository(BaseRepository[PairLock]):
    """Consultas para bloqueos de pairs."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(PairLock, session_manager)

    def get_active_locks(self) -> list[PairLock]:
        session = self._session()
        return list(session.execute(select(PairLock).where(PairLock.active)).scalars().all())

    def get_active_locks_for_pair(self, pair: str) -> list[PairLock]:
        session = self._session()
        return list(
            session.execute(select(PairLock).where(PairLock.pair == pair, PairLock.active))
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# Repositorio de Estrategias
# ---------------------------------------------------------------------------


class StrategyRepository(BaseRepository[Strategy]):
    """Consultas para estrategias."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(Strategy, session_manager)

    def get_by_name(self, name: str) -> Strategy | None:
        session = self._session()
        return session.execute(select(Strategy).where(Strategy.name == name)).scalar_one_or_none()

    def get_active_strategies(self) -> list[Strategy]:
        session = self._session()
        return list(session.execute(select(Strategy).where(Strategy.is_active)).scalars().all())


# ---------------------------------------------------------------------------
# Repositorio de Notificaciones
# ---------------------------------------------------------------------------


class NotificationSettingRepository(BaseRepository[NotificationSetting]):
    """Consultas para configuraciones de notificaciones."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(NotificationSetting, session_manager)

    def get_by_user(self, user_id: int) -> list[NotificationSetting]:
        session = self._session()
        return list(
            session.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user_id)
            )
            .scalars()
            .all()
        )

    def get_enabled_by_user(self, user_id: int) -> list[NotificationSetting]:
        session = self._session()
        return list(
            session.execute(
                select(NotificationSetting).where(
                    NotificationSetting.user_id == user_id,
                    NotificationSetting.is_enabled,
                )
            )
            .scalars()
            .all()
        )


# ---------------------------------------------------------------------------
# Repositorio de Auditoría
# ---------------------------------------------------------------------------


class AuditLogRepository(BaseRepository[AuditLog]):
    """Consultas para logs de auditoría."""

    def __init__(self, session_manager: ISessionManager) -> None:
        super().__init__(AuditLog, session_manager)

    def get_by_user(self, user_id: int, limit: int = 100) -> list[AuditLog]:
        session = self._session()
        return list(
            session.execute(
                select(AuditLog)
                .where(AuditLog.user_id == user_id)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def get_by_entity(self, entity_type: str, entity_id: int) -> list[AuditLog]:
        session = self._session()
        return list(
            session.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
                .order_by(AuditLog.created_at.desc())
            )
            .scalars()
            .all()
        )
