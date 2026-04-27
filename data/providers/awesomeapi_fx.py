from __future__ import annotations
import requests
from datetime import datetime
 
from config.settings import FX_URL, USER_AGENT
from core.models import FxQuote
 
 
# Provedores alternativos de FX (gratuitos, sem chave) usados como fallback
# quando a AwesomeAPI retorna 429 (rate limit) ou falha por outro motivo.
_FALLBACK_PROVIDERS = (
    "https://open.er-api.com/v6/latest/USD",
    "https://api.exchangerate.host/latest?base=USD&symbols=BRL",
)
 
 
def _from_awesomeapi() -> FxQuote:
    r = requests.get(FX_URL, timeout=15, headers=USER_AGENT)
    r.raise_for_status()
    data = r.json()["USDBRL"]
    usd_brl = float(data["bid"])
    fx_ts = datetime.fromtimestamp(int(data["timestamp"])).isoformat(timespec="seconds")
    return FxQuote(usd_brl=usd_brl, fx_ts=fx_ts)
 
 
def _from_fallback(url: str) -> FxQuote:
    r = requests.get(url, timeout=15, headers=USER_AGENT)
    r.raise_for_status()
    data = r.json()
    rates = data.get("rates") or {}
    brl = rates.get("BRL")
    if brl is None:
        raise ValueError(f"BRL ausente em {url}")
    fx_ts = datetime.now().isoformat(timespec="seconds")
    return FxQuote(usd_brl=float(brl), fx_ts=fx_ts)
 
 
def fetch_usd_brl() -> FxQuote:
    """
    Tenta AwesomeAPI primeiro. Em caso de 429 ou falha, usa provedores
    alternativos (open.er-api.com, exchangerate.host) para nao quebrar o fluxo.
    """
    last_err = None
    try:
        return _from_awesomeapi()
    except Exception as e:
        last_err = e
 
    for url in _FALLBACK_PROVIDERS:
        try:
            return _from_fallback(url)
        except Exception as e:
            last_err = e
            continue
 
    raise RuntimeError(
        f"Falha em todas as fontes de USD/BRL (AwesomeAPI + fallbacks). "
        f"Ultimo erro: {last_err}"
    )
