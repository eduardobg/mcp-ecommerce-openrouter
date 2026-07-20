"""Construccion de la base SQLite a partir del CSV (equivalente al Paso 3 del notebook)."""

import sqlite3
from pathlib import Path

import pandas as pd


def build_database(csv_path: Path, db_path: Path) -> None:
    """
    Crea (o reconstruye) la tabla `orders` en SQLite a partir del CSV.

    Idempotente: si `db_path` ya existe y es mas reciente que `csv_path`,
    no se reconstruye.
    """
    if db_path.exists() and db_path.stat().st_mtime >= csv_path.stat().st_mtime:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    df["Order_Date"] = pd.to_datetime(df["Order_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        df.to_sql("orders", conn, if_exists="replace", index=False)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(Customer_ID)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_country ON orders(Country)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_segment ON orders(Customer_Segment)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(Order_Date)")
