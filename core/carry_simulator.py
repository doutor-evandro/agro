from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


HORIZONS: Tuple[int, ...] = (3, 6, 9)


@dataclass(frozen=True)
class CarryScenario:
    commodity: str
    months: int
    sacks: float
    price_today_input: float
    price_today_net: float
    capital_discount_pct: float
    funrural_discount_pct: float
    cdi_monthly_pct: float
    future_price_expected_input: float
    future_price_net_adjusted: float
    receipt_today_total: float
    fv_sell_now_cdi_unit: float
    fv_sell_now_cdi_total: float
    sell_future_total: float
    breakeven_future_price_input: float
    diff_total: float
    diff_pct: float
    decision: str


@dataclass(frozen=True)
class FloorPriceScenario:
    commodity: str
    months: int
    sacks: float
    price_today_input: float
    price_today_net: float
    capital_discount_pct: float
    funrural_discount_pct: float
    cdi_monthly_pct: float
    risk_discount_total_pct: float
    fv_sell_now_cdi_unit: float
    fv_sell_now_cdi_total: float
    min_future_price_input: float
    pct_up_vs_today_input: float
    future_total_at_floor: float


def simulate_scenarios(
    commodity: str,
    price_today: float,
    cdi_monthly_pct: float,
    expected_prices: Dict[int, float],
    sacks: float = 1.0,
    capital_discount_pct: float = 0.0,
    funrural_discount_pct: float = 0.0,
    risk_discount_total_pct: float = 0.0,
) -> List[CarryScenario]:
    if price_today <= 0 or sacks <= 0:
        return []

    total_discount_pct = max(0.0, capital_discount_pct) + max(0.0, funrural_discount_pct)
    discount_factor = max(0.0, 1.0 - total_discount_pct / 100.0)
    risk_factor = max(0.0, 1.0 - max(0.0, risk_discount_total_pct) / 100.0)
    price_today_net = price_today * discount_factor
    receipt_today_total = price_today_net * sacks

    scenarios: List[CarryScenario] = []
    for months in HORIZONS:
        future_exp = float(expected_prices.get(months, 0.0) or 0.0)
        if future_exp <= 0:
            continue

        future_net_adj_unit = future_exp * discount_factor * risk_factor
        fv_now_unit = _future_value(price_today_net, cdi_monthly_pct, months)
        fv_now_total = fv_now_unit * sacks
        future_total = future_net_adj_unit * sacks

        diff_total = fv_now_total - future_total
        diff_pct = (diff_total / future_total * 100.0) if future_total > 0 else 0.0
        decision = "VENDER HOJE" if diff_total >= 0 else "ESPERAR"
        breakeven_future_input = _safe_div(fv_now_unit, (discount_factor * risk_factor))

        scenarios.append(
            CarryScenario(
                commodity=commodity,
                months=months,
                sacks=sacks,
                price_today_input=price_today,
                price_today_net=price_today_net,
                capital_discount_pct=capital_discount_pct,
                funrural_discount_pct=funrural_discount_pct,
                cdi_monthly_pct=cdi_monthly_pct,
                future_price_expected_input=future_exp,
                future_price_net_adjusted=future_net_adj_unit,
                receipt_today_total=receipt_today_total,
                fv_sell_now_cdi_unit=fv_now_unit,
                fv_sell_now_cdi_total=fv_now_total,
                sell_future_total=future_total,
                breakeven_future_price_input=breakeven_future_input,
                diff_total=diff_total,
                diff_pct=diff_pct,
                decision=decision,
            )
        )
    return scenarios


def minimum_future_price_scenarios(
    commodity: str,
    price_today: float,
    cdi_monthly_pct: float,
    sacks: float = 1.0,
    capital_discount_pct: float = 0.0,
    funrural_discount_pct: float = 0.0,
    risk_discount_total_pct: float = 0.0,
) -> List[FloorPriceScenario]:
    if price_today <= 0 or sacks <= 0:
        return []

    total_discount_pct = max(0.0, capital_discount_pct) + max(0.0, funrural_discount_pct)
    discount_factor = max(0.0, 1.0 - total_discount_pct / 100.0)
    risk_factor = max(0.0, 1.0 - max(0.0, risk_discount_total_pct) / 100.0)
    price_today_net = price_today * discount_factor

    scenarios: List[FloorPriceScenario] = []
    for months in HORIZONS:
        fv_now_unit = _future_value(price_today_net, cdi_monthly_pct, months)
        fv_now_total = fv_now_unit * sacks

        min_input = _safe_div(fv_now_unit, (discount_factor * risk_factor))
        pct_up = ((min_input / price_today) - 1.0) * 100.0 if price_today > 0 else 0.0
        future_total_floor = min_input * discount_factor * risk_factor * sacks

        scenarios.append(
            FloorPriceScenario(
                commodity=commodity,
                months=months,
                sacks=sacks,
                price_today_input=price_today,
                price_today_net=price_today_net,
                capital_discount_pct=capital_discount_pct,
                funrural_discount_pct=funrural_discount_pct,
                cdi_monthly_pct=cdi_monthly_pct,
                risk_discount_total_pct=risk_discount_total_pct,
                fv_sell_now_cdi_unit=fv_now_unit,
                fv_sell_now_cdi_total=fv_now_total,
                min_future_price_input=min_input,
                pct_up_vs_today_input=pct_up,
                future_total_at_floor=future_total_floor,
            )
        )
    return scenarios


def summarize_recommendation(scenarios: List[CarryScenario]) -> str:
    if not scenarios:
        return "Sem dados suficientes para recomendacao."

    n_sell = sum(1 for s in scenarios if s.decision == "VENDER HOJE")
    n_wait = len(scenarios) - n_sell

    if n_sell == len(scenarios):
        return "VENDER AGORA (CDI supera todos os cenarios futuros informados)."
    if n_wait == len(scenarios):
        return "NAO VENDER AGORA (esperar supera CDI em todos os cenarios)."
    return "VENDA PARCIAL (resultado misto entre vender hoje e esperar)."


def _future_value(price_today: float, monthly_rate_pct: float, months: int) -> float:
    rate = monthly_rate_pct / 100.0
    return price_today * ((1.0 + rate) ** months)


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b
