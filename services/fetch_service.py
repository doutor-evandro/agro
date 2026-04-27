from __future__ import annotations

from core.models import CommodityQuote, Snapshot
from core.utils import now_iso
from core.calc import soja_em_reais

from data.providers.noticias_agricolas import fetch_milho_quote, fetch_soja_quote
from data.providers.awesomeapi_fx import fetch_usd_brl


def fetch_snapshot() -> Snapshot:
    ts = now_iso()

    mc, mp, mch, masof, mtick = fetch_milho_quote()
    sc, sp, sch, sasof, stick = fetch_soja_quote()
    fx = fetch_usd_brl()

    milho = CommodityQuote(contract_label=mc, price=mp, change_pct=mch, asof=masof, ticker_calc=mtick)
    soja = CommodityQuote(contract_label=sc, price=sp, change_pct=sch, asof=sasof, ticker_calc=stick)

    soja_brl = soja_em_reais(soja.price, fx.usd_brl)

    source = "Notícias Agrícolas (Fonte: B3) + AwesomeAPI (USD/BRL)"

    return Snapshot(ts=ts, milho=milho, soja=soja, fx=fx, soja_brl=soja_brl, source=source)
