from __future__ import annotations

import csv
import io
import json
import sqlite3
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from config.settings import DB_PATH, JSON_DB_PATH, USER_AGENT, BUNDLED_JSON_DB_PATH
from core.models import Snapshot


Point = Tuple[datetime, float, float, float, float]
SACKS_PER_TON = 1000.0 / 60.0
FRED_MILHO_SERIES = "PMAIZMTUSDM"
FRED_SOJA_SERIES = "PSOYBUSDM"
FRED_FX_SERIES = "DEXBZUS"


def _default_payload() -> dict:
    return {"version": 1, "history": []}


def _read_payload() -> dict:
    if not Path(JSON_DB_PATH).exists():
        return _default_payload()
    try:
        with open(JSON_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "history" not in data:
            return _default_payload()
        if not isinstance(data["history"], list):
            return _default_payload()
        return data
    except Exception:
        return _default_payload()


def _write_payload(payload: dict) -> None:
    Path(JSON_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=Path(JSON_DB_PATH).parent) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)
    tmp_path.replace(JSON_DB_PATH)


def _upsert_points(payload: dict, rows: List[dict]) -> int:
    by_ts = {}
    for item in payload.get("history", []):
        ts = item.get("ts")
        if isinstance(ts, str) and ts:
            by_ts[ts] = item

    changed = 0
    for row in rows:
        ts = row["ts"]
        prev = by_ts.get(ts)
        if prev != row:
            by_ts[ts] = row
            changed += 1

    payload["history"] = [by_ts[k] for k in sorted(by_ts)]
    return changed


def init_json_store() -> None:
    _bootstrap_json_from_bundle()
    payload = _read_payload()
    changed = 0
    changed += _sync_from_sqlite(payload)
    changed += _seed_two_year_history(payload)
    if changed > 0 or not Path(JSON_DB_PATH).exists():
        _write_payload(payload)


def _bootstrap_json_from_bundle() -> None:
    src = Path(BUNDLED_JSON_DB_PATH)
    dst = Path(JSON_DB_PATH)

    if not src.exists():
        return
    try:
        if src.resolve() == dst.resolve():
            return
    except Exception:
        pass

    src_count = _json_history_count(src)
    dst_count = _json_history_count(dst) if dst.exists() else -1

    # Keep user data if it is already richer than bundled seed data.
    if dst_count >= src_count:
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _json_history_count(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        history = data.get("history", []) if isinstance(data, dict) else []
        return len(history) if isinstance(history, list) else 0
    except Exception:
        return 0


def append_snapshot(s: Snapshot) -> None:
    payload = _read_payload()
    row = {
        "ts": s.ts,
        "milho": float(s.milho.price),
        "soja_usd": float(s.soja.price),
        "usd_brl": float(s.fx.usd_brl),
        "soja_brl": float(s.soja_brl),
        "source": "live",
    }
    ch = _upsert_points(payload, [row])
    ch += _sync_from_sqlite(payload)
    if ch > 0:
        _write_payload(payload)


def ensure_history_synced() -> None:
    """
    Garante que snapshots do SQLite entram no JSON antes de ler o historico.
    Evita grafico vazio quando o KPI veio do SQLite mas o arquivo JSON estava
    defasado (ex.: Streamlit Cloud, falha silenciosa no append, ou sync perdido).
    """
    payload = _read_payload()
    if _sync_from_sqlite(payload) > 0:
        _write_payload(payload)


def series_history() -> List[Point]:
    ensure_history_synced()
    payload = _read_payload()
    out: List[Point] = []
    for row in payload.get("history", []):
        try:
            ts = datetime.fromisoformat(row["ts"])
            milho = float(row["milho"])
            soja_usd = float(row["soja_usd"])
            usd_brl = float(row["usd_brl"])
            soja_brl = float(row["soja_brl"])
            out.append((ts, milho, soja_usd, usd_brl, soja_brl))
        except Exception:
            continue
    return sorted(out, key=lambda p: p[0])


def _sync_from_sqlite(payload: dict) -> int:
    query = """
        SELECT ts, milho_price, soja_price_usd, usd_brl, COALESCE(soja_brl, soja_price_usd * usd_brl)
        FROM snapshots
        ORDER BY ts ASC
    """
    try:
        with sqlite3.connect(DB_PATH) as con:
            rows = con.execute(query).fetchall()
    except Exception:
        return 0

    points = []
    for ts, milho, soja_usd, usd_brl, soja_brl in rows:
        points.append(
            {
                "ts": str(ts),
                "milho": float(milho),
                "soja_usd": float(soja_usd),
                "usd_brl": float(usd_brl),
                "soja_brl": float(soja_brl),
                "source": "sqlite",
            }
        )
    return _upsert_points(payload, points)


def _seed_two_year_history(payload: dict) -> int:
    cutoff = datetime.now().date().replace(day=1)
    existing_old = False
    for row in payload.get("history", []):
        try:
            d = datetime.fromisoformat(row["ts"]).date()
            if d <= _shift_month(cutoff, -24):
                existing_old = True
                break
        except Exception:
            continue
    if existing_old:
        return 0

    try:
        milho_usd_ton = _fetch_fred_series(FRED_MILHO_SERIES)
        soja_usd_ton = _fetch_fred_series(FRED_SOJA_SERIES)
        usd_brl_daily = _fetch_fred_series(FRED_FX_SERIES)
    except Exception:
        return 0

    fx_by_month = _monthly_last(usd_brl_daily)
    points = []
    start = _shift_month(cutoff, -24)
    current = start
    while current <= cutoff:
        month_key = current.strftime("%Y-%m")
        fred_key = current.strftime("%Y-%m-01")
        milho_ton = milho_usd_ton.get(fred_key)
        soja_ton = soja_usd_ton.get(fred_key)
        fx = fx_by_month.get(month_key)
        if milho_ton is not None and soja_ton is not None and fx is not None:
            milho_usd_sc = milho_ton / SACKS_PER_TON
            soja_usd_sc = soja_ton / SACKS_PER_TON
            milho_brl_sc = milho_usd_sc * fx
            soja_brl_sc = soja_usd_sc * fx
            points.append(
                {
                    "ts": f"{fred_key}T00:00:00",
                    "milho": float(milho_brl_sc),
                    "soja_usd": float(soja_usd_sc),
                    "usd_brl": float(fx),
                    "soja_brl": float(soja_brl_sc),
                    "source": "fred_monthly",
                }
            )
        current = _shift_month(current, 1)

    return _upsert_points(payload, points)


def _fetch_fred_series(series_id: str) -> Dict[str, float]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    # Timeout menor no cold start evita travar a primeira carga no Streamlit Cloud se FRED estiver lento.
    resp = requests.get(url, timeout=15, headers=USER_AGENT)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    value_key = series_id
    out: Dict[str, float] = {}
    for row in reader:
        d = row.get("observation_date")
        v = row.get(value_key)
        if not d or not v or v == ".":
            continue
        out[d] = float(v)
    return out


def _monthly_last(daily_series: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for d in sorted(daily_series):
        out[d[:7]] = float(daily_series[d])
    return out


def _shift_month(d: date, delta_months: int) -> date:
    idx = (d.year * 12 + (d.month - 1)) + delta_months
    year = idx // 12
    month = idx % 12 + 1
    return date(year, month, 1)
