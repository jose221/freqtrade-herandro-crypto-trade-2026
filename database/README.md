# Capa de Base de Datos PostgreSQL para Freqtrade

Integración completa de Freqtrade con PostgreSQL usando SQLAlchemy 2.x, principios SOLID,
pool de conexiones optimizado y una capa de repositorios para todas las consultas.

---

## Estructura del paquete

```
database/
├── __init__.py           # Exports públicos del paquete
├── interfaces.py         # Abstracciones SOLID (IConnectionProvider, ISessionManager, IRepository)
├── config.py             # Configuración immutable desde variables de entorno
├── connection.py         # DatabaseConnection: engine PostgreSQL + QueuePool anti-fugas
├── session.py            # DatabaseSessionManager: scoped_session por hilo/request
├── models.py             # Modelos ER SQLAlchemy (todas las entidades)
├── repositories.py       # Capa de consulta: un repositorio por entidad
├── bootstrap.py          # Punto de entrada único: init_postgres(), get_repositories()
├── .env.example          # Plantilla de variables de entorno
├── migrations/
│   ├── 001_initial_schema.sql           # Schema completo + datos iniciales
│   └── 002_migrate_sqlite_to_postgres.sql  # Guía de migración SQLite → PostgreSQL
└── scripts/
    └── export_sqlite.py  # Exporta SQLite a CSV para importar en PostgreSQL
```

---

## Modelo ER

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MODELO ENTIDAD-RELACIÓN                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐       ┌──────────────────────┐
│    users     │       │    user_sessions      │
├──────────────┤  1:N  ├──────────────────────┤
│ id (PK)      │───────│ id (PK)              │
│ username     │       │ user_id (FK→users)   │
│ email        │       │ refresh_token_hash   │
│ hashed_pass  │       │ expires_at           │
│ role         │       │ ip_address           │
│ is_active    │       │ user_agent           │
│ created_at   │       └──────────────────────┘
│ updated_at   │
└──────┬───────┘
       │ 1:N
       │
┌──────▼───────┐       ┌──────────────────────┐
│     bots     │  1:1  │     bot_configs       │
├──────────────┤───────├──────────────────────┤
│ id (PK)      │       │ id (PK)              │
│ owner_id(FK) │       │ bot_id (FK→bots)     │
│ name         │       │ max_open_trades      │
│ status       │       │ stake_currency       │
│ dry_run      │       │ stake_amount         │
│ created_at   │       │ tradable_balance_ratio│
│ updated_at   │       │ fiat_display_currency│
└──────┬───────┘       │ timeframe            │
       │               │ strategy             │
       │               │ initial_state        │
       │               │ force_entry_enable   │
       │               │ cancel_open_orders   │
       │               │ unfilledtimeout(JSONB)│
       │               │ entry_pricing (JSONB)│
       │               │ exit_pricing  (JSONB)│
       │               │ pairlists     (JSONB)│
       │               │ internals     (JSONB)│
       │               │ extra_config  (JSONB)│
       │               └──────────────────────┘
       │
       │ 1:1           ┌──────────────────────┐
       ├───────────────│ exchange_credentials  │
       │               ├──────────────────────┤
       │               │ id (PK)              │
       │               │ bot_id (FK→bots)     │
       │               │ exchange_name        │
       │               │ api_key_encrypted    │
       │               │ api_secret_encrypted │
       │               │ ccxt_config   (JSONB)│
       │               │ pair_whitelist(JSONB)│
       │               │ pair_blacklist(JSONB)│
       │               └──────────────────────┘
       │
       │ 1:N           ┌──────────────────────┐       ┌──────────────────┐
       └───────────────│       trades          │  1:N  │     orders       │
                       ├──────────────────────┤───────├──────────────────┤
                       │ id (PK)              │       │ id (PK)          │
                       │ bot_id (FK→bots)     │       │ trade_id (FK)    │
                       │ exchange             │       │ ft_order_side    │
                       │ pair                 │       │ ft_pair          │
                       │ base_currency        │       │ ft_is_open       │
                       │ stake_currency       │       │ order_id         │
                       │ is_open              │       │ status           │
                       │ open_rate            │       │ order_type       │
                       │ close_rate           │       │ side             │
                       │ stake_amount         │       │ price            │
                       │ amount               │       │ filled           │
                       │ open_date            │       │ order_date       │
                       │ close_date           │       │ funding_fee      │
                       │ stop_loss            │       └──────────────────┘
                       │ exit_reason          │
                       │ strategy             │
                       │ leverage             │
                       │ is_short             │
                       └──────────────────────┘

┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│      pairlocks       │   │      strategies       │   │   key_value_store    │
├──────────────────────┤   ├──────────────────────┤   ├──────────────────────┤
│ id (PK)              │   │ id (PK)              │   │ id (PK)              │
│ pair                 │   │ name (UNIQUE)        │   │ key (UNIQUE)         │
│ side                 │   │ description          │   │ value_type           │
│ reason               │   │ version              │   │ string_value         │
│ lock_time            │   │ parameters (JSONB)   │   │ float_value          │
│ lock_end_time        │   │ is_active            │   │ int_value            │
│ active               │   └──────────────────────┘   │ datetime_value       │
└──────────────────────┘                               └──────────────────────┘

┌──────────────────────────────┐   ┌──────────────────────────────┐
│    notification_settings     │   │         audit_logs            │
├──────────────────────────────┤   ├──────────────────────────────┤
│ id (PK)                      │   │ id (PK, BIGSERIAL)           │
│ user_id (FK→users)           │   │ user_id (FK→users, nullable) │
│ channel (telegram/email/wh)  │   │ action                       │
│ is_enabled                   │   │ entity_type                  │
│ config (JSONB)               │   │ entity_id                    │
│ UNIQUE(user_id, channel)     │   │ details (JSONB)              │
└──────────────────────────────┘   │ ip_address                   │
                                   │ created_at                   │
                                   └──────────────────────────────┘
```

---

## Instalación

### 1. Instalar dependencias

```bash
pip install psycopg2-binary sqlalchemy
# O con el driver async:
pip install asyncpg
```

### 2. Crear la base de datos en PostgreSQL

```sql
CREATE USER freqtrade_user WITH PASSWORD 'cambiar_password';
CREATE DATABASE freqtrade_db OWNER freqtrade_user;
GRANT ALL PRIVILEGES ON DATABASE freqtrade_db TO freqtrade_user;
```

### 3. Configurar variables de entorno

```bash
cp database/.env.example database/.env
# Editar database/.env con tus credenciales reales
```

### 4. Ejecutar la migración initial

```bash
psql -U freqtrade_user -d freqtrade_db -f database/migrations/001_initial_schema.sql
```

### 5. Configurar Freqtrade para usar PostgreSQL

En `config.json`, cambiar la URL de base de datos:

```json
{
    "db_url": "postgresql+psycopg2://freqtrade_user:cambiar_password@localhost:5432/freqtrade_db"
}
```

O al lanzar el bot:

```bash
freqtrade trade --config config.json \
    --db-url "postgresql+psycopg2://freqtrade_user:cambiar_password@localhost:5432/freqtrade_db"
```

---

## Migración desde SQLite

### Paso 1: Exportar datos de SQLite

```bash
python database/scripts/export_sqlite.py \
    --sqlite tradesv3.dryrun.sqlite \
    --output-dir /tmp \
    --bot-id 1
```

### Paso 2: Importar en PostgreSQL

Editar `database/migrations/002_migrate_sqlite_to_postgres.sql`,
descomentar los bloques `COPY` y ejecutar:

```bash
psql -U freqtrade_user -d freqtrade_db -f database/migrations/002_migrate_sqlite_to_postgres.sql
```

---

## Uso desde código Python

```python
from database.bootstrap import init_postgres, get_repositories, shutdown_postgres
from database.config import DatabaseConfig

# Inicializar (una sola vez al arrancar la app)
init_postgres()  # Lee FREQTRADE_DB_URL del entorno

# O con URL explícita:
cfg = DatabaseConfig.from_url(
    "postgresql+psycopg2://freqtrade_user:pass@localhost:5432/freqtrade_db"
)
init_postgres(cfg)

# Obtener repositorios
repos = get_repositories()

# Consultar trades abiertos del bot 1
open_trades = repos.trades.get_open_trades(bot_id=1)

# Usar session_scope para transacciones
from database.bootstrap import get_session_manager
sm = get_session_manager()

with sm.session_scope() as session:
    user = repos.users.get_by_username("freqtrader")
    user.is_active = True
    # commit automático al salir del with

# Al apagar la aplicación
shutdown_postgres()
```

---

## Principios SOLID aplicados

| Principio | Implementación |
|-----------|---------------|
| **S** - Single Responsibility | Cada clase tiene una sola responsabilidad: `DatabaseConnection` solo gestiona el pool, `DatabaseSessionManager` solo gestiona sesiones, cada repositorio solo consulta su entidad. |
| **O** - Open/Closed | Nuevos repositorios extienden `BaseRepository` sin modificarlo. Nuevas entidades se agregan en `models.py` sin tocar el resto. |
| **L** - Liskov Substitution | `DatabaseConnection` implementa completamente `IConnectionProvider`. `DatabaseSessionManager` implementa completamente `ISessionManager`. |
| **I** - Interface Segregation | `IConnectionProvider`, `ISessionManager` e `IRepository` son interfaces pequeñas y específicas. |
| **D** - Dependency Inversion | Los repositorios dependen de `ISessionManager` (abstracción), no de `DatabaseSessionManager` (implementación). `bootstrap.py` inyecta las dependencias. |

---

## Prevención de fugas de conexiones

| Mecanismo | Descripción |
|-----------|-------------|
| `pool_pre_ping=True` | Verifica que la conexión esté viva antes de entregarla |
| `pool_recycle=1800` | Recicla conexiones cada 30 min (evita timeouts del servidor) |
| `pool_size=10` | Máximo de conexiones permanentes en el pool |
| `max_overflow=20` | Conexiones extra permitidas en picos de carga |
| `pool_timeout=30` | Máximo 30s esperando una conexión disponible |
| `session_scope()` | Commit/rollback/remove automático en cada transacción |
| `scoped_session` | Una sesión por hilo/request, liberada con `remove_session()` |
