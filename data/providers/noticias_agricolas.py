from __future__ import annotations
import re
from datetime import date
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup

from config.settings import NA_URLS, USER_AGENT
from core.tickers import ticker_vigente
from core.utils import parse_float_br, safe_float_br


PT_MONTH = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,  # sem acento (HTML as vezes normaliza)
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _extract_table_rows(html: str) -> Tuple[str, List[Tuple[str, float, Optional[float]]]]:
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n", strip=True)
    m = re.search(r"Fechamento:\s*(\d{2}/\d{2}/\d{4})", text)
    asof = f"Fechamento: {m.group(1)}" if m else "Fechamento: (não identificado)"

    tables = soup.find_all("table")
    chosen = None
    for t in tables:
        ths = " ".join([th.get_text(" ", strip=True).lower() for th in t.find_all("th")])
        if "contrato" in ths and "fechamento" in ths:
            chosen = t
            break
    if chosen is None:
        raise RuntimeError("Não encontrei tabela de cotações (layout pode ter mudado).")

    rows = []
    for tr in chosen.find_all("tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 2:
            continue
        contract = tds[0]
        price = parse_float_br(tds[1])
        change = safe_float_br(tds[2]) if len(tds) >= 3 else None
        rows.append((contract, price, change))

    if not rows:
        raise RuntimeError("Tabela encontrada, mas sem linhas de dados.")
    return asof, rows


def _contract_to_month_year(contract_label: str) -> Optional[Tuple[int, int]]:
    parts = contract_label.strip().lower().split("/")
    if len(parts) != 2:
        return None
    month_name = parts[0].strip()
    year_str = re.sub(r"\D", "", parts[1])
    if month_name not in PT_MONTH or not year_str:
        return None
    return PT_MONTH[month_name], int(year_str)


def pick_nearest_contract(rows: List[Tuple[str, float, Optional[float]]]) -> Tuple[str, float, Optional[float]]:
    today = date.today()
    scored = []
    for (label, price, chg) in rows:
        my = _contract_to_month_year(label)
        if not my:
            continue
        m, y = my
        ref = date(y, m, 15)  # aproximação
        delta = (ref - today).days
        if delta >= -10:
            scored.append((abs(delta), delta, label, price, chg))
    if scored:
        scored.sort(key=lambda x: (x[0], x[1]))
        _, _, label, price, chg = scored[0]
        return label, price, chg
    return rows[0][0], rows[0][1], rows[0][2]


def fetch_milho_quote():
    url = NA_URLS["MILHO"]
    resp = requests.get(url, timeout=20, headers=USER_AGENT)
    resp.raise_for_status()

    asof, rows = _extract_table_rows(resp.text)
    contract, price, chg = pick_nearest_contract(rows)

    return contract, price, chg, asof, ticker_vigente("CCM")


def fetch_soja_quote():
    url = NA_URLS["SOJA"]
    resp = requests.get(url, timeout=20, headers=USER_AGENT)
    resp.raise_for_status()

    asof, rows = _extract_table_rows(resp.text)
    contract, price, chg = pick_nearest_contract(rows)

    return contract, price, chg, asof, ticker_vigente("SJC")
