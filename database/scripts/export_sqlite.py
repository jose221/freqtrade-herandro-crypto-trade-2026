"""
Script de exportación de datos SQLite → CSV para migración a PostgreSQL.
Exporta todas las tablas nativas de Freqtrade a archivos CSV en /tmp/.

Uso:
    python database/scripts/export_sqlite.py --sqlite tradesv3.dryrun.sqlite --bot-id 1
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


TABLES_TO_EXPORT = {
    "trades": [
        "id",
        "exchange",
        "pair",
        "base_currency",
        "stake_currency",
        "is_open",
        "fee_open",
        "fee_open_cost",
        "fee_open_currency",
        "fee_close",
        "fee_close_cost",
        "fee_close_currency",
        "open_rate",
        "open_rate_requested",
        "open_trade_value",
        "close_rate",
        "close_rate_requested",
        "realized_profit",
        "close_profit",
        "close_profit_abs",
        "stake_amount",
        "max_stake_amount",
        "amount",
        "amount_requested",
        "open_date",
        "close_date",
        "open_order_id",
        "stop_loss",
        "stop_loss_pct",
        "initial_stop_loss",
        "initial_stop_loss_pct",
        "is_stop_loss_trailing",
        "stoploss_order_id",
        "stoploss_last_update",
        "max_rate",
        "min_rate",
        "exit_reason",
        "exit_order_status",
        "strategy",
        "enter_tag",
        "timeframe",
        "trading_mode",
        "amount_precision",
        "price_precision",
        "precision_mode",
        "contract_size",
        "leverage",
        "is_short",
        "liquidation_price",
        "funding_fees",
        "interest_rate",
    ],
    "orders": [
        "id",
        "trade_id",
        "ft_order_side",
        "ft_pair",
        "ft_is_open",
        "ft_amount",
        "ft_price",
        "order_id",
        "status",
        "symbol",
        "order_type",
        "side",
        "price",
        "average",
        "amount",
        "filled",
        "remaining",
        "cost",
        "stop_price",
        "order_date",
        "order_filled_date",
        "order_update_date",
        "funding_fee",
        "ft_fee_base",
    ],
    "pairlocks": [
        "id",
        "pair",
        "side",
        "reason",
        "lock_time",
        "lock_end_time",
        "active",
    ],
    "trade_custom_data": [
        "id",
        "ft_trade_id",
        "cd_key",
        "cd_type",
        "cd_value",
        "created_at",
        "updated_at",
    ],
}


def get_existing_columns(cursor: sqlite3.Cursor, table: str) -> list[str]:
    """Retorna las columnas que realmente existen en la tabla SQLite."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def export_table(
    cursor: sqlite3.Cursor,
    table: str,
    columns: list[str],
    output_dir: Path,
    bot_id: int,
) -> int:
    """Exporta una tabla a CSV. Retorna el número de filas exportadas."""
    existing = get_existing_columns(cursor, table)
    valid_columns = [c for c in columns if c in existing]

    if not valid_columns:
        print(f"  [SKIP] Tabla '{table}' no encontrada o sin columnas válidas.")
        return 0

    output_file = output_dir / f"{table}_export.csv"
    cols_sql = ", ".join(valid_columns)

    # Para trades, agregar bot_id como columna extra
    if table == "trades":
        cursor.execute(f"SELECT {cols_sql} FROM {table}")
        rows = cursor.fetchall()
        with output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["bot_id"] + valid_columns)
            for row in rows:
                writer.writerow([bot_id] + list(row))
    else:
        cursor.execute(f"SELECT {cols_sql} FROM {table}")
        rows = cursor.fetchall()
        with output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(valid_columns)
            writer.writerows(rows)

    print(f"  [OK] {table}: {len(rows)} filas → {output_file}")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta tablas de Freqtrade SQLite a CSV para migración a PostgreSQL."
    )
    parser.add_argument(
        "--sqlite",
        default="tradesv3.dryrun.sqlite",
        help="Ruta al archivo SQLite de Freqtrade (default: tradesv3.dryrun.sqlite)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / ".freqtrade" / "exports"),
        help="Directorio de salida para los CSV (default: ~/.freqtrade/exports)",
    )
    parser.add_argument(
        "--bot-id",
        type=int,
        default=1,
        help="ID del bot en PostgreSQL al que se asignarán los trades (default: 1)",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"ERROR: No se encontró el archivo SQLite: {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nExportando datos de: {sqlite_path}")
    print(f"Directorio de salida: {output_dir}")
    print(f"Bot ID destino: {args.bot_id}\n")

    conn = sqlite3.connect(str(sqlite_path))
    cursor = conn.cursor()

    total_rows = 0
    for table, columns in TABLES_TO_EXPORT.items():
        total_rows += export_table(cursor, table, columns, output_dir, args.bot_id)

    conn.close()

    print(f"\nExportación completada. Total de filas: {total_rows}")
    print("\nPróximos pasos:")
    print("  1. Ejecutar en PostgreSQL: database/migrations/001_initial_schema.sql")
    print(
        "  2. Descomentar y ajustar los COPY en: "
        "database/migrations/002_migrate_sqlite_to_postgres.sql"
    )
    print("  3. Ejecutar: database/migrations/002_migrate_sqlite_to_postgres.sql")


if __name__ == "__main__":
    main()
