"""Smoke tests: imports, storage bootstrap e núcleo analítico sem UI."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_settings_paths_exist():
    from pathlib import Path

    from config import settings

    assert settings.APP_TITLE
    assert isinstance(settings.APP_DIR, Path)
    assert settings.DB_PATH.suffix == ".sqlite"
    assert settings.JSON_DB_PATH.name == "agro_history.json"


def test_sqlite_json_bootstrap(tmp_path):
    """Processo isolado: evita reload de settings que quebraria outros testes."""
    script = """
import os
from pathlib import Path
from data.storage.sqlite_store import init_db
from data.storage.json_store import init_json_store

root = Path(os.environ["AGRO_DATA_DIR"]).resolve()
init_db()
init_json_store()
assert (root / "agro_quotes.sqlite").exists()
assert (root / "agro_history.json").exists()
"""
    env = {**os.environ, "AGRO_DATA_DIR": str(tmp_path), "PYTHONPATH": str(_REPO_ROOT)}
    r = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_analyze_market_synthetic_points():
    from core.stat_analysis import analyze_market

    base = datetime(2025, 1, 1, 12, 0, 0)
    points = []
    for i in range(30):
        t = base + timedelta(days=i)
        milho = 70.0 + i * 0.01
        soja_usd = 12.0 + i * 0.005
        usd = 5.0 + i * 0.001
        soja_brl = soja_usd * usd
        points.append((t, milho, soja_usd, usd, soja_brl))

    stats_list, cross, profile, lots = analyze_market(
        points,
        window_days=21,
        min_points=8,
        profile_name="moderado",
        sell_lots=(20, 30, 50),
    )
    assert len(stats_list) >= 1
    assert profile.name == "moderado"
    assert sum(lots) == 100


@pytest.mark.integration
def test_fetch_snapshot_live():
    """Rede externa (Notícias Agrícolas + FX). Opcional em CI sem internet."""
    from services.fetch_service import fetch_snapshot

    snap = fetch_snapshot()
    assert snap.milho.price > 0
    assert snap.soja.price > 0
    assert snap.fx.usd_brl > 0
    assert snap.soja_brl > 0


@pytest.mark.integration
def test_providers_parse_or_skip():
    """Smoke nas fontes HTTP (pode falhar por rate limit / HTML alterado)."""
    from data.providers.awesomeapi_fx import fetch_usd_brl

    fx = fetch_usd_brl()
    assert fx.usd_brl > 4.0
    assert fx.usd_brl < 10.0
