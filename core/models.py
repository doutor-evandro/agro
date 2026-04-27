from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CommodityQuote:
    contract_label: str
    price: float
    change_pct: Optional[float]
    asof: str
    ticker_calc: str


@dataclass(frozen=True)
class FxQuote:
    usd_brl: float
    fx_ts: str


@dataclass(frozen=True)
class Snapshot:
    ts: str

    milho: CommodityQuote
    soja: CommodityQuote
    fx: FxQuote

    soja_brl: float  # derivado (soja_usd * usdbrl)
    source: str
