from __future__ import annotations
import sqlite3
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

from config.settings import DB_PATH, BUNDLED_DB_PATH
from core.models import Snapshot


def _ensure_schema(con: sqlite3.Connection) -> None:
    cols = {row[1] for row in con.execute("PRAGMA table_info(snapshots)").fetchall()}
    if "soja_brl" not in cols:
        con.execute("ALTER TABLE snapshots ADD COLUMN soja_brl REAL;")
        # Backfill from existing columns for legacy databases.
        con.execute("""
            UPDATE snapshots
            SET soja_brl = soja_price_usd * usd_brl
            WHERE soja_brl IS NULL
        """)


def init_db() -> None:
    _bootstrap_db_from_bundle()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,

            milho_contract TEXT NOT NULL,
            milho_ticker_calc TEXT NOT NULL,
            milho_price REAL NOT NULL,
            milho_change_pct REAL,
            milho_asof TEXT,

            soja_contract TEXT NOT NULL,
            soja_ticker_calc TEXT NOT NULL,
            soja_price_usd REAL NOT NULL,
            soja_change_pct REAL,
            soja_asof TEXT,

            usd_brl REAL NOT NULL,
            fx_ts TEXT,

            soja_brl REAL NOT NULL,

            source TEXT
        );
        """)
        _ensure_schema(con)
        con.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);")


def _bootstrap_db_from_bundle() -> None:
    src = Path(BUNDLED_DB_PATH)
    dst = Path(DB_PATH)

    if not src.exists():
        return
    try:
        if src.resolve() == dst.resolve():
            return
    except Exception:
        pass

    src_count = _sqlite_snapshot_count(src)
    dst_count = _sqlite_snapshot_count(dst) if dst.exists() else -1

    # Keep user data if it is already richer than bundled seed data.
    if dst_count >= src_count:
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _sqlite_snapshot_count(path: Path) -> int:
    try:
        with sqlite3.connect(path) as con:
            row = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def insert_snapshot(s: Snapshot) -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
        INSERT INTO snapshots(
            ts,
            milho_contract, milho_ticker_calc, milho_price, milho_change_pct, milho_asof,
            soja_contract, soja_ticker_calc, soja_price_usd, soja_change_pct, soja_asof,
            usd_brl, fx_ts,
            soja_brl,
            source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            s.ts,
            s.milho.contract_label, s.milho.ticker_calc, s.milho.price, s.milho.change_pct, s.milho.asof,
            s.soja.contract_label, s.soja.ticker_calc, s.soja.price, s.soja.change_pct, s.soja.asof,
            s.fx.usd_brl, s.fx.fx_ts,
            s.soja_brl,
            s.source
        ))


def last_snapshot() -> Optional[Snapshot]:
    from core.models import CommodityQuote, FxQuote  # evitar import circular

    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("""
        SELECT ts,
               milho_contract, milho_ticker_calc, milho_price, milho_change_pct, milho_asof,
               soja_contract, soja_ticker_calc, soja_price_usd, soja_change_pct, soja_asof,
               usd_brl, fx_ts,
               soja_brl,
               source
        FROM snapshots
        ORDER BY ts DESC
        LIMIT 1
        """).fetchone()

    if not row:
        return None

    ts = row[0]
    milho = CommodityQuote(row[1], float(row[3]), (float(row[4]) if row[4] is not None else None), row[5] or "", row[2])
    soja = CommodityQuote(row[6], float(row[8]), (float(row[9]) if row[9] is not None else None), row[10] or "", row[7])
    fx = FxQuote(float(row[11]), row[12] or "")
    soja_brl = float(row[13]) if row[13] is not None else float(row[8]) * float(row[11])
    source = row[14] or ""

    return Snapshot(ts=ts, milho=milho, soja=soja, fx=fx, soja_brl=soja_brl, source=source)


def series_soja_brl() -> List[Tuple[datetime, float, float, float]]:
    """
    Retorna lista de pontos:
    (dt, soja_brl, soja_usd, usd_brl)
    """
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute("""
            SELECT ts, soja_brl, soja_price_usd, usd_brl
            FROM snapshots
            ORDER BY ts ASC
        """).fetchall()

    out = []
    for ts, soja_brl, soja_usd, usd_brl in rows:
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        soja_brl_val = float(soja_brl) if soja_brl is not None else float(soja_usd) * float(usd_brl)
        out.append((dt, soja_brl_val, float(soja_usd), float(usd_brl)))
    return out
