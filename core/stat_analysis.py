from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Dict, List, Tuple


Point = Tuple[datetime, float, float, float, float]


@dataclass(frozen=True)
class AnalysisProfile:
    name: str
    ret_threshold_pct: float
    ma_gap_threshold_pct: float
    high_vol_threshold_pct: float
    deep_drawdown_threshold_pct: float
    zscore_extreme: float


@dataclass(frozen=True)
class SeriesStats:
    label: str
    window_label: str
    n_points: int
    start_ts: datetime
    end_ts: datetime
    start_value: float
    end_value: float
    return_pct: float
    slope_per_day: float
    r2: float
    ma_fast: float
    ma_slow: float
    ma_gap_pct: float
    vol_step_pct: float
    max_drawdown_pct: float
    zscore_last: float
    regime: str
    decision: str
    score: int


@dataclass(frozen=True)
class CrossMarketStats:
    window_label: str
    n_points: int
    corr_soja_fx: float
    corr_soja_brl_fx: float
    corr_soja_brl_soja: float
    corr_milho_soja_brl: float


PROFILES: Dict[str, AnalysisProfile] = {
    "conservador": AnalysisProfile(
        name="conservador",
        ret_threshold_pct=1.8,
        ma_gap_threshold_pct=0.7,
        high_vol_threshold_pct=1.6,
        deep_drawdown_threshold_pct=-4.5,
        zscore_extreme=1.4,
    ),
    "moderado": AnalysisProfile(
        name="moderado",
        ret_threshold_pct=1.0,
        ma_gap_threshold_pct=0.4,
        high_vol_threshold_pct=2.0,
        deep_drawdown_threshold_pct=-6.0,
        zscore_extreme=1.8,
    ),
    "agressivo": AnalysisProfile(
        name="agressivo",
        ret_threshold_pct=0.5,
        ma_gap_threshold_pct=0.2,
        high_vol_threshold_pct=2.8,
        deep_drawdown_threshold_pct=-8.0,
        zscore_extreme=2.4,
    ),
}


def list_profiles() -> Tuple[str, ...]:
    return tuple(PROFILES.keys())


def analyze_market(
    points: List[Point],
    window_days: int = 21,
    min_points: int = 8,
    profile_name: str = "conservador",
    sell_lots: Tuple[int, int, int] = (20, 30, 50),
) -> Tuple[List[SeriesStats], CrossMarketStats | None, AnalysisProfile, Tuple[int, int, int]]:
    profile = PROFILES.get(profile_name, PROFILES["moderado"])
    lots = _normalize_lots(sell_lots)

    datasets = {
        "MILHO (R$/sc)": [(p[0], p[1]) for p in points],
        "SOJA (US$/sc)": [(p[0], p[2]) for p in points],
        "USD/BRL": [(p[0], p[3]) for p in points],
        "SOJA (R$/sc)": [(p[0], p[4]) for p in points],
    }

    stats_list: List[SeriesStats] = []
    for label, series in datasets.items():
        s = _analyze_series(
            label,
            series,
            window_days=window_days,
            min_points=min_points,
            profile=profile,
            sell_lots=lots,
        )
        if s is not None:
            stats_list.append(s)

    cross = _cross_market_stats(points, window_days=window_days, min_points=min_points)
    return stats_list, cross, profile, lots


def build_report(
    points: List[Point],
    window_days: int = 21,
    min_points: int = 8,
    profile_name: str = "conservador",
    sell_lots: Tuple[int, int, int] = (20, 30, 50),
) -> str:
    if not points:
        return "Analise estatistica: sem dados no historico."

    stats_list, cross, profile, lots = analyze_market(
        points,
        window_days=window_days,
        min_points=min_points,
        profile_name=profile_name,
        sell_lots=sell_lots,
    )

    lines = [
        "ANALISE ESTATISTICA PARA TOMADA DE DECISAO",
        "Base teorica: momentum + regressao linear + medias moveis + volatilidade + drawdown + z-score.",
        f"Gerado em: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Perfil de risco: {profile.name}",
        f"Plano de venda soja (lotes): {lots[0]}/{lots[1]}/{lots[2]}",
        "",
    ]

    stats_map = {s.label: s for s in stats_list}
    for label in ("MILHO (R$/sc)", "SOJA (US$/sc)", "USD/BRL", "SOJA (R$/sc)"):
        s = stats_map.get(label)
        if s is None:
            lines.extend([f"[{label}]", "Dados insuficientes.", ""])
            continue
        lines.extend(_series_lines(s))
        lines.append("")

    lines.extend(_cross_market_lines(cross))
    return "\n".join(lines).strip() + "\n"


def _analyze_series(
    label: str,
    series: List[Tuple[datetime, float]],
    window_days: int,
    min_points: int,
    profile: AnalysisProfile,
    sell_lots: Tuple[int, int, int],
) -> SeriesStats | None:
    selected, window_label = _select_window(series, window_days=window_days, min_points=min_points)
    if len(selected) < 3:
        return None

    selected = sorted(selected, key=lambda x: x[0])
    ts = [t for t, _ in selected]
    vals = [float(v) for _, v in selected]

    start_v = vals[0]
    end_v = vals[-1]
    ret_pct = ((end_v / start_v) - 1.0) * 100.0 if start_v > 0 else 0.0

    slope, r2 = _linear_trend(ts, vals)

    fast_n = min(5, len(vals))
    slow_n = min(15, len(vals))
    ma_fast = mean(vals[-fast_n:])
    ma_slow = mean(vals[-slow_n:])
    ma_gap_pct = ((ma_fast / ma_slow) - 1.0) * 100.0 if ma_slow > 0 else 0.0

    step_returns = [((vals[i] / vals[i - 1]) - 1.0) * 100.0 for i in range(1, len(vals)) if vals[i - 1] > 0]
    vol_step_pct = pstdev(step_returns) if len(step_returns) >= 2 else 0.0
    mdd = _max_drawdown_pct(vals)

    mu = mean(vals)
    sigma = pstdev(vals) if len(vals) >= 2 else 0.0
    z_last = ((end_v - mu) / sigma) if sigma > 0 else 0.0

    regime, decision, score = _classify_regime(
        ret_pct=ret_pct,
        slope=slope,
        ma_gap_pct=ma_gap_pct,
        vol_step_pct=vol_step_pct,
        max_drawdown_pct=mdd,
        zscore_last=z_last,
        label=label,
        profile=profile,
        sell_lots=sell_lots,
    )

    return SeriesStats(
        label=label,
        window_label=window_label,
        n_points=len(vals),
        start_ts=ts[0],
        end_ts=ts[-1],
        start_value=start_v,
        end_value=end_v,
        return_pct=ret_pct,
        slope_per_day=slope,
        r2=r2,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        ma_gap_pct=ma_gap_pct,
        vol_step_pct=vol_step_pct,
        max_drawdown_pct=mdd,
        zscore_last=z_last,
        regime=regime,
        decision=decision,
        score=score,
    )


def _series_lines(s: SeriesStats) -> List[str]:
    return [
        f"[{s.label}]",
        f"Janela: {s.window_label} | Pontos: {s.n_points}",
        f"Periodo: {s.start_ts:%Y-%m-%d %H:%M:%S} -> {s.end_ts:%Y-%m-%d %H:%M:%S}",
        f"Nivel: {s.start_value:.4f} -> {s.end_value:.4f} ({s.return_pct:+.2f}%)",
        f"Tendencia linear: slope={s.slope_per_day:+.4f} por dia | R2={s.r2:.3f}",
        f"Medias moveis: MA5={s.ma_fast:.4f} | MA15={s.ma_slow:.4f} | Gap={s.ma_gap_pct:+.2f}%",
        (
            f"Risco: vol(step)={s.vol_step_pct:.2f}% | max drawdown={s.max_drawdown_pct:.2f}% "
            f"| zscore atual={s.zscore_last:+.2f}"
        ),
        f"Regime: {s.regime} | Score: {s.score:+d}",
        f"Sinal decisao: {s.decision}",
    ]


def _cross_market_stats(points: List[Point], window_days: int, min_points: int) -> CrossMarketStats | None:
    selected, label = _select_window([(p[0], 0.0) for p in points], window_days=window_days, min_points=min_points)
    if not selected:
        return None

    ts_allowed = {t for t, _ in selected}
    sample = [p for p in points if p[0] in ts_allowed]
    if len(sample) < 3:
        return None

    soja_usd = [p[2] for p in sample]
    usd_brl = [p[3] for p in sample]
    soja_brl = [p[4] for p in sample]
    milho = [p[1] for p in sample]

    return CrossMarketStats(
        window_label=label,
        n_points=len(sample),
        corr_soja_fx=_corr(soja_usd, usd_brl),
        corr_soja_brl_fx=_corr(soja_brl, usd_brl),
        corr_soja_brl_soja=_corr(soja_brl, soja_usd),
        corr_milho_soja_brl=_corr(milho, soja_brl),
    )


def _cross_market_lines(cross: CrossMarketStats | None) -> List[str]:
    if cross is None:
        return ["[CROSS-MARKET]", "Dados insuficientes para correlacao."]

    return [
        "[CROSS-MARKET]",
        f"Janela: {cross.window_label} | Pontos: {cross.n_points}",
        f"Correlacao Soja(US$) x USD/BRL: {cross.corr_soja_fx:+.3f}",
        f"Correlacao Soja(R$) x USD/BRL: {cross.corr_soja_brl_fx:+.3f}",
        f"Correlacao Soja(R$) x Soja(US$): {cross.corr_soja_brl_soja:+.3f}",
        f"Correlacao Milho(R$) x Soja(R$): {cross.corr_milho_soja_brl:+.3f}",
    ]


def _select_window(
    series: List[Tuple[datetime, float]], window_days: int, min_points: int
) -> Tuple[List[Tuple[datetime, float]], str]:
    if not series:
        return [], "sem dados"

    cutoff = datetime.now() - timedelta(days=window_days)
    recent = [p for p in series if p[0] >= cutoff]
    if len(recent) >= min_points:
        return recent, f"ultimos {window_days} dias"

    fallback_n = min(max(min_points, 5), len(series))
    return series[-fallback_n:], f"ultimos {fallback_n} registros (fallback)"


def _linear_trend(ts: List[datetime], vals: List[float]) -> Tuple[float, float]:
    x = [(t - ts[0]).total_seconds() / 86400.0 for t in ts]
    y = vals
    x_mean = mean(x)
    y_mean = mean(y)
    den = sum((xi - x_mean) ** 2 for xi in x)
    if den == 0:
        return 0.0, 0.0
    slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / den

    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum((yi - (y_mean + slope * (xi - x_mean))) ** 2 for xi, yi in zip(x, y))
    r2 = 0.0 if ss_tot == 0 else max(0.0, 1.0 - (ss_res / ss_tot))
    return slope, r2


def _max_drawdown_pct(vals: List[float]) -> float:
    peak = vals[0]
    worst = 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            dd = ((v / peak) - 1.0) * 100.0
            if dd < worst:
                worst = dd
    return worst


def _corr(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    ma = mean(a)
    mb = mean(b)
    sa = pstdev(a)
    sb = pstdev(b)
    if sa == 0 or sb == 0:
        return 0.0
    cov = mean([(x - ma) * (y - mb) for x, y in zip(a, b)])
    return cov / (sa * sb)


def _normalize_lots(lots: Tuple[int, int, int]) -> Tuple[int, int, int]:
    a, b, c = lots
    vals = [max(1, int(a)), max(1, int(b)), max(1, int(c))]
    total = sum(vals)
    if total == 100:
        return vals[0], vals[1], vals[2]

    n1 = int(round(vals[0] * 100 / total))
    n2 = int(round(vals[1] * 100 / total))
    n3 = 100 - n1 - n2
    if n3 <= 0:
        n3 = 1
        n2 = max(1, 99 - n1)
    return n1, n2, n3


def _classify_regime(
    ret_pct: float,
    slope: float,
    ma_gap_pct: float,
    vol_step_pct: float,
    max_drawdown_pct: float,
    zscore_last: float,
    label: str,
    profile: AnalysisProfile,
    sell_lots: Tuple[int, int, int],
) -> Tuple[str, str, int]:
    score = 0
    if ret_pct >= profile.ret_threshold_pct:
        score += 1
    elif ret_pct <= -profile.ret_threshold_pct:
        score -= 1

    if slope > 0:
        score += 1
    elif slope < 0:
        score -= 1

    if ma_gap_pct >= profile.ma_gap_threshold_pct:
        score += 1
    elif ma_gap_pct <= -profile.ma_gap_threshold_pct:
        score -= 1

    if max_drawdown_pct <= profile.deep_drawdown_threshold_pct:
        score -= 1
    if vol_step_pct >= profile.high_vol_threshold_pct:
        score -= 1

    if score >= 2:
        regime = "Alta com momentum"
    elif score <= -2:
        regime = "Baixa com pressao"
    else:
        regime = "Lateral/Transicao"

    if label != "SOJA (R$/sc)":
        if score >= 2:
            return regime, "Regime favoravel de alta; monitorar continuidade do movimento.", score
        if score <= -2:
            return regime, "Regime fragil; evitar aumento de exposicao direcional.", score
        return regime, "Regime neutro; manter gestao de risco e aguardar confirmacao.", score

    l1, l2, l3 = sell_lots
    if score >= 2 and zscore_last <= profile.zscore_extreme:
        decision = (
            f"Plano {l1}/{l2}/{l3}: vender {l1}% agora; "
            f"vender {l2}% se MA5 > MA15 e preco subir +1.0%; "
            f"vender {l3}% com trailing stop de 2.0% abaixo da maxima recente."
        )
    elif score <= -2:
        decision = (
            f"Plano defensivo {l1}/{l2}/{l3}: vender {l1 + l2}% imediatamente; "
            f"manter {l3}% com stop tecnico de 1.5% abaixo da minima recente."
        )
    else:
        decision = (
            f"Plano neutro {l1}/{l2}/{l3}: vender {l1}% agora; "
            f"vender {l2}% se rompimento (+0.8%) ou em 5 dias; "
            f"vender {l3}% no primeiro sinal de perda da MA5."
        )

    return regime, decision, score
