from __future__ import annotations
import requests
from datetime import datetime

from config.settings import FX_URL, USER_AGENT
from core.models import FxQuote


def fetch_usd_brl() -> FxQuote:
    """
    Usa AwesomeAPI (USD-BRL). 'bid' como referência.
    """
    r = requests.get(FX_URL, timeout=15, headers=USER_AGENT)
    r.raise_for_status()
    data = r.json()["USDBRL"]
    usd_brl = float(data["bid"])
    fx_ts = datetime.fromtimestamp(int(data["timestamp"])).isoformat(timespec="seconds")
    return FxQuote(usd_brl=usd_brl, fx_ts=fx_ts)
