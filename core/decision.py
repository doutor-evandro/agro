from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import List, Tuple


Point = Tuple[datetime, float, float, float, float]


@dataclass(frozen=True)
class SoyTrendAnalysis:
    selection_label: str
    n_points: int
    start_ts: datetime
    end_ts: datetime
    start_price: float
    end_price: float
    pct_change: float
    slope_per_day: float
    ma_short: float
    ma_long: float
    volatility_pct: float
    trend: str
    action: str
    confidence: str


def select_window_points(points: List[Point], window_days: int = 14, min_points: int = 5) -> Tuple[List[Point], str]:
    if not points:
        return [], "sem dados"

    cutoff = datetime.now() - timedelta(days=window_days)
    recent = [p for p in points if p[0] >= cutoff]
    if len(recent) >= min_points:
        return recent, f"ultimos {window_days} dias"

    fallback_n = min(max(min_points, 2), len(points))
    return points[-fallback_n:], f"ultimos {fallback_n} registros (fallback)"


def analyze_soy_trend(points: List[Point], window_days: int = 14, min_points: int = 5) -> SoyTrendAnalysis | None:
    selected, label = select_window_points(points, window_days=window_days, min_points=min_points)
    if len(selected) < 2:
        return None

    selected = sorted(selected, key=lambda p: p[0])
    ts = [p[0] for p in selected]
    soja_brl = [p[4] for p in selected]

    start_p = soja_brl[0]
    end_p = soja_brl[-1]
    pct_change = ((end_p / start_p) - 1.0) * 100.0 if start_p > 0 else 0.0

    x = [(t - ts[0]).total_seconds() / 86400.0 for t in ts]
    y = soja_brl
    x_mean = mean(x)
    y_mean = mean(y)
    den = sum((xi - x_mean) ** 2 for xi in x)
    slope = 0.0 if den == 0 else sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / den

    short_n = min(3, len(y))
    long_n = min(7, len(y))
    ma_short = mean(y[-short_n:])
    ma_long = mean(y[-long_n:])

    rets = [((y[i] / y[i - 1]) - 1.0) * 100.0 for i in range(1, len(y)) if y[i - 1] > 0]
    vol = pstdev(rets) if len(rets) >= 2 else 0.0

    score = 0
    if pct_change >= 1.0:
        score += 1
    if pct_change <= -1.0:
        score -= 1
    if slope > 0:
        score += 1
    if slope < 0:
        score -= 1
    if ma_short > ma_long * 1.002:
        score += 1
    if ma_short < ma_long * 0.998:
        score -= 1

    if score >= 2:
        trend = "alta"
        action = "Segurar parte e vender em lotes com alvo e stop de protecao."
    elif score <= -2:
        trend = "baixa"
        action = "Aumentar venda parcial e reduzir risco de queda adicional."
    else:
        trend = "lateral"
        action = "Fazer venda escalonada (parcelas) para reduzir incerteza."

    if len(selected) >= 10 and vol < 1.8:
        confidence = "alta"
    elif len(selected) >= 5:
        confidence = "media"
    else:
        confidence = "baixa"

    return SoyTrendAnalysis(
        selection_label=label,
        n_points=len(selected),
        start_ts=ts[0],
        end_ts=ts[-1],
        start_price=start_p,
        end_price=end_p,
        pct_change=pct_change,
        slope_per_day=slope,
        ma_short=ma_short,
        ma_long=ma_long,
        volatility_pct=vol,
        trend=trend,
        action=action,
        confidence=confidence,
    )


def analysis_to_text(a: SoyTrendAnalysis | None) -> str:
    if a is None:
        return "Analise 14d: dados insuficientes para calcular tendencia."

    return (
        f"Janela: {a.selection_label} | Pontos: {a.n_points}\n"
        f"Soja R$/sc: {a.start_price:.2f} -> {a.end_price:.2f} ({a.pct_change:+.2f}%)\n"
        f"Medias moveis: curta={a.ma_short:.2f} | longa={a.ma_long:.2f} | inclinacao={a.slope_per_day:+.3f} R$/dia\n"
        f"Volatilidade: {a.volatility_pct:.2f}% | Tendencia: {a.trend.upper()} | Confianca: {a.confidence.upper()}\n"
        f"Acao sugerida: {a.action}"
    )
