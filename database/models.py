"""
Modelos ER extendidos para Freqtrade + PostgreSQL.
Incluye: usuarios, bots, configuraciones, exchanges, pairs, estrategias,
         notificaciones, auditoría y las tablas nativas de Freqtrade.

Principios SOLID:
  - Single Responsibility: cada clase representa una sola entidad del dominio.
  - Open/Closed: extensible agregando nuevas entidades sin modificar las existentes.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base declarativa compartida
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------


class UserRole(StrEnum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class BotStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    EXPIRED = "expired"


class NotificationChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"


# ---------------------------------------------------------------------------
# Entidades de usuarios y autenticación
# ---------------------------------------------------------------------------


class User(Base):
    """
    Usuario del sistema. Puede gestionar uno o más bots.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.TRADER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    bots: Mapped[list["Bot"]] = relationship(
        "Bot", back_populates="owner", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")
    notification_settings: Mapped[list["NotificationSetting"]] = relationship(
        "NotificationSetting", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} role={self.role}>"


class UserSession(Base):
    """
    Sesiones activas de usuario (tokens JWT refresh).
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship("User")


# ---------------------------------------------------------------------------
# Entidades de bots y configuración
# ---------------------------------------------------------------------------


class Bot(Base):
    """
    Instancia de bot Freqtrade. Un usuario puede tener múltiples bots.
    """

    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[BotStatus] = mapped_column(
        Enum(BotStatus, name="bot_status"), nullable=False, default=BotStatus.STOPPED
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    owner: Mapped["User"] = relationship("User", back_populates="bots")
    config: Mapped["BotConfig"] = relationship(
        "BotConfig", back_populates="bot", uselist=False, cascade="all, delete-orphan"
    )
    trades: Mapped[list["Trade"]] = relationship(
        "Trade", back_populates="bot", cascade="all, delete-orphan"
    )
    exchange_credential: Mapped["ExchangeCredential"] = relationship(
        "ExchangeCredential", back_populates="bot", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_bot_owner_name"),)

    def __repr__(self) -> str:
        return f"<Bot id={self.id} name={self.name} status={self.status}>"


class BotConfig(Base):
    """
    Configuración completa de un bot (equivalente al config.json).
    Almacenada como JSONB para flexibilidad y consultas eficientes.
    """

    __tablename__ = "bot_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    max_open_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    stake_currency: Mapped[str] = mapped_column(String(20), nullable=False, default="USDT")
    stake_amount: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=30.0)
    tradable_balance_ratio: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False, default=0.99
    )
    fiat_display_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="5m")
    strategy: Mapped[str] = mapped_column(String(128), nullable=False, default="SampleStrategy")
    initial_state: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    force_entry_enable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancel_open_orders_on_exit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Configuraciones complejas almacenadas como JSONB
    unfilledtimeout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    entry_pricing: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    exit_pricing: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    pairlists: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    internals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extra_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["Bot"] = relationship("Bot", back_populates="config")

    def __repr__(self) -> str:
        return f"<BotConfig bot_id={self.bot_id} strategy={self.strategy}>"


class ExchangeCredential(Base):
    """
    Credenciales de exchange por bot. Las claves se almacenan cifradas.
    NUNCA almacenar claves en texto plano en producción.
    """

    __tablename__ = "exchange_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    exchange_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Claves cifradas (usar pgcrypto o cifrado en capa de aplicación)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    ccxt_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pair_whitelist: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pair_blacklist: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    bot: Mapped["Bot"] = relationship("Bot", back_populates="exchange_credential")

    def __repr__(self) -> str:
        return f"<ExchangeCredential bot_id={self.bot_id} exchange={self.exchange_name}>"


# ---------------------------------------------------------------------------
# Entidades de trading (equivalentes a las tablas nativas de Freqtrade)
# ---------------------------------------------------------------------------


class Trade(Base):
    """
    Trade ejecutado por un bot. Equivalente a la tabla 'trades' de Freqtrade,
    extendida con referencia al bot propietario.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(64), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    stake_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    fee_open: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    fee_open_cost: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    fee_open_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fee_close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    fee_close_cost: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    fee_close_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    open_rate: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    open_rate_requested: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    open_trade_value: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    close_rate: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    close_rate_requested: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    realized_profit: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    close_profit: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    close_profit_abs: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    stake_amount: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    max_stake_amount: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    amount_requested: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    open_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stop_loss: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    stop_loss_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    initial_stop_loss: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    initial_stop_loss_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    is_stop_loss_trailing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stoploss_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stoploss_last_update: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_rate: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    min_rate: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exit_order_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enter_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeframe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_mode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    liquidation_price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    funding_fees: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    interest_rate: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)

    # Relaciones
    bot: Mapped["Bot"] = relationship("Bot", back_populates="trades")
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="trade", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_trades_bot_pair_open", "bot_id", "pair", "is_open"),
        Index("ix_trades_open_date", "open_date"),
    )

    def __repr__(self) -> str:
        return f"<Trade id={self.id} pair={self.pair} is_open={self.is_open}>"


class Order(Base):
    """
    Orden de exchange asociada a un trade.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ft_order_side: Mapped[str] = mapped_column(String(25), nullable=False)
    ft_pair: Mapped[str] = mapped_column(String(20), nullable=False)
    ft_is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ft_amount: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    ft_price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    order_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(25), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    side: Mapped[str | None] = mapped_column(String(25), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    average: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    filled: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    remaining: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    cost: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    order_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_filled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    order_update_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    funding_fee: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0.0)
    ft_fee_base: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)

    trade: Mapped["Trade"] = relationship("Trade", back_populates="orders")

    __table_args__ = (UniqueConstraint("order_id", "ft_pair", name="uq_order_id_pair"),)

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_id={self.order_id} side={self.side}>"


class PairLock(Base):
    """
    Bloqueo de pair de trading (evita abrir trades en pairs bloqueados).
    """

    __tablename__ = "pairlocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(25), nullable=False, default="*")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lock_end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    def __repr__(self) -> str:
        return f"<PairLock pair={self.pair} active={self.active} until={self.lock_end_time}>"


# ---------------------------------------------------------------------------
# Entidades de estrategias
# ---------------------------------------------------------------------------


class Strategy(Base):
    """
    Registro de estrategias disponibles y sus parámetros.
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Strategy name={self.name} version={self.version}>"


# ---------------------------------------------------------------------------
# Entidades de notificaciones
# ---------------------------------------------------------------------------


class NotificationSetting(Base):
    """
    Configuración de notificaciones por usuario (Telegram, email, webhook).
    """

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Configuración específica del canal (token, chat_id, email, url, etc.)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="notification_settings")

    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_notification_user_channel"),)

    def __repr__(self) -> str:
        return f"<NotificationSetting user_id={self.user_id} channel={self.channel}>"


# ---------------------------------------------------------------------------
# Auditoría
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """
    Registro de auditoría de acciones de usuarios sobre bots y configuraciones.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} user_id={self.user_id}>"


# ---------------------------------------------------------------------------
# Key-Value store (equivalente al de Freqtrade)
# ---------------------------------------------------------------------------


class KeyValueStore(Base):
    """
    Almacén clave-valor para datos internos del bot (equivalente a _KeyValueStoreModel).
    """

    __tablename__ = "key_value_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    string_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    float_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    int_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    datetime_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<KeyValueStore key={self.key}>"
