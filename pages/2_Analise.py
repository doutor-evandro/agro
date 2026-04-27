"""
Pagina Analise - analise estatistica multivariada com semaforo, tabela, graficos e relatorio.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd
import streamlit as st

from core.stat_analysis import analyze_market, build_report, list_profiles
from data.storage.json_store import init_json_store, series_history
from data.storage.sqlite_store import init_db


@st.cache_resource(show_spinner=False)
def _bootstrap():
    init_db()
    init_json_store()
    return True


_bootstrap()
st.set_page_config(page_title="Analise", layout="wide")
st.title("Analise Estatistica")
st.caption(
    "Resumo multivariado por serie (Soja, Milho, USD/BRL e Soja em R$). "
    "Semaforo: VERDE = alta, AMARELO = transicao, VERMELHO = baixa."
)

# ---------- Inputs ----------
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    days = st.selectbox(
        "Janela (dias)",
        options=[14, 21, 30, 45, 60, 90],
        index=1,
    )
with c2:
    profile = st.selectbox("Perfil", options=list_profiles(), index=0)
with c3:
    lots_text = st.text_input(
        "Lotes soja (formato A/B/C, soma <=100)",
        value="20/30/50",
        help="3 fracoes em pontos percentuais para escalonar a venda da soja.",
    )


def _parse_lots(value: str) -> tuple[int, int, int]:
    if not value:
        return 20, 30, 50
    text = value.replace(" ", "").replace("-", "/").replace(",", "/")
    parts = [p for p in text.split("/") if p]
    if len(parts) != 3:
        return 20, 30, 50
    try:
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        if a <= 0 or b <= 0 or c <= 0:
            return 20, 30, 50
        return a, b, c
    except Exception:
        return 20, 30, 50


lots = _parse_lots(lots_text)

# ---------- Run ----------
points = series_history()
if not points:
    st.warning("Sem historico carregado. Va ate Dashboard e clique em 'Atualizar agora'.")
    st.stop()

stats_list, cross, _, used_lots = analyze_market(
    points,
    window_days=int(days),
    min_points=8,
    profile_name=profile.lower(),
    sell_lots=lots,
)
report_text = build_report(
    points,
    window_days=int(days),
    min_points=8,
    profile_name=profile.lower(),
    sell_lots=used_lots,
)


# ---------- Decisoes destacadas ----------
def _find(label: str):
    for s in stats_list:
        if s.label == label:
            return s
    return None


def _decision_soja(s):
    if s is None:
        return "SOJA: sem dados suficientes."
    if s.score >= 2:
        return "SOJA: NAO VENDER TOTAL. Venda parcial em lotes e manter saldo protegido."
    if s.score == 1:
        return "SOJA: VENDA PARCIAL. Realizar parte agora e manter parte com gatilhos."
    if s.score <= -2:
        return "SOJA: VENDA FORTE (quase total). Reduzir risco de queda adicional."
    return "SOJA: VENDA PARCIAL CONSERVADORA. Reduzir exposicao e aguardar confirmacao."


def _decision_milho(s):
    if s is None:
        return "MILHO: sem dados suficientes."
    if s.score >= 2 and s.vol_step_pct < 1.8:
        return "MILHO: NAO VENDER AGORA. Tendencia favorece alta; monitorar risco."
    if s.score >= 1:
        return "MILHO: VENDA PARCIAL LEVE. Realizar parte para travar margem."
    if s.score <= -2:
        return "MILHO: VENDA TOTAL ou quase total. Regime de baixa com pressao."
    return "MILHO: VENDA PARCIAL. Regime de transicao com protecao."


def _decision_dolar(s):
    if s is None:
        return "DOLAR: sem dados suficientes."
    if s.score >= 1:
        return "DOLAR: COMPRA"
    return "DOLAR: VENDA"


st.subheader("Decisoes em Destaque")
soja = _find("SOJA (R$/sc)")
milho = _find("MILHO (R$/sc)")
dolar = _find("USD/BRL")

st.markdown(f"**{_decision_soja(soja)}**")
st.markdown(f"**{_decision_milho(milho)}**")
st.markdown(f"**{_decision_dolar(dolar)}**")

# ---------- Tabela resumo ----------
st.subheader("Resumo Estruturado")


def _semaphore(score: int) -> str:
    if score >= 2:
        return "VERDE"
    if score <= -2:
        return "VERMELHO"
    return "AMARELO"


rows = []
for s in stats_list:
    rows.append(
        {
            "Serie": s.label,
            "Semaforo": _semaphore(s.score),
            "Retorno %": f"{s.return_pct:+.2f}",
            "MA gap %": f"{s.ma_gap_pct:+.2f}",
            "Vol %": f"{s.vol_step_pct:.2f}",
            "Drawdown %": f"{s.max_drawdown_pct:.2f}",
            "Score": f"{s.score:+d}",
            "Regime": s.regime,
        }
    )
if cross is not None:
    rows.append(
        {
            "Serie": "CROSS: SojaR$ x USD/BRL",
            "Semaforo": "N/A",
            "Retorno %": "-",
            "MA gap %": "-",
            "Vol %": "-",
            "Drawdown %": "-",
            "Score": "-",
            "Regime": f"corr={cross.corr_soja_brl_fx:+.3f}",
        }
    )

df = pd.DataFrame(rows)


def _row_color(row):
    sem = row["Semaforo"]
    if sem == "VERDE":
        return ["background-color: #e8f5e9"] * len(row)
    if sem == "AMARELO":
        return ["background-color: #fffde7"] * len(row)
    if sem == "VERMELHO":
        return ["background-color: #ffebee"] * len(row)
    return ["background-color: #f5f5f5"] * len(row)


st.dataframe(df.style.apply(_row_color, axis=1), use_container_width=True, hide_index=True)

# ---------- Graficos ----------
st.subheader("Visual Rapido")


def _short(label: str) -> str:
    if label == "SOJA (R$/sc)":
        return "SOJA-BR"
    return label.replace(" (R$/sc)", "").replace(" (US$/sc)", "")


if stats_list:
    fig, (ax_ret, ax_risk) = plt.subplots(1, 2, figsize=(11, 4.5))
    labels = [_short(s.label) for s in stats_list]
    ret = [s.return_pct for s in stats_list]
    colors = ["#2e7d32" if v >= 0 else "#c62828" for v in ret]
    bars = ax_ret.bar(labels, ret, color=colors)
    ax_ret.axhline(0, color="#333", linewidth=1)
    ax_ret.set_title("Retorno da Janela (%)")
    ax_ret.set_ylabel("%")
    ax_ret.tick_params(axis="x", rotation=20)
    for b, v in zip(bars, ret):
        ax_ret.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{v:+.2f}%",
            ha="center",
            va="bottom" if v >= 0 else "top",
            fontsize=8,
        )

    x = [s.vol_step_pct for s in stats_list]
    y = [s.return_pct for s in stats_list]
    size = [120 + 40 * abs(s.score) for s in stats_list]
    c = [s.score for s in stats_list]
    ax_risk.scatter(x, y, s=size, c=c, cmap="RdYlGn", vmin=-4, vmax=4, alpha=0.85, edgecolors="black")
    for i, s in enumerate(stats_list):
        ax_risk.annotate(_short(s.label), (x[i], y[i]), textcoords="offset points", xytext=(6, 5), fontsize=8)
    ax_risk.axhline(0, color="#333", linewidth=1)
    ax_risk.axvline(0, color="#333", linewidth=1)
    ax_risk.set_title("Mapa Risco x Retorno")
    ax_risk.set_xlabel("Volatilidade por passo (%)")
    ax_risk.set_ylabel("Retorno da janela (%)")
    ax_risk.grid(True, alpha=0.25)
    ax_risk.legend(
        handles=[
            Line2D([0], [0], marker="o", color="w", label="Verde: score positivo", markerfacecolor="#2e7d32", markersize=7),
            Line2D([0], [0], marker="o", color="w", label="Amarelo: score neutro", markerfacecolor="#f9a825", markersize=7),
            Line2D([0], [0], marker="o", color="w", label="Vermelho: score negativo", markerfacecolor="#c62828", markersize=7),
        ],
        loc="lower right",
        frameon=True,
        fontsize=7,
        title="Legenda",
        title_fontsize=8,
    )
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)

# ---------- Relatorio completo ----------
with st.expander("Relatorio Completo (texto)"):
    st.text(report_text or "Sem relatorio.")

# ---------- Exportar TXT ----------
st.download_button(
    "Baixar relatorio (.txt)",
    data=(report_text or "").encode("utf-8"),
    file_name=f"analise_{profile.lower()}_{int(days)}d.txt",
    mime="text/plain",
)

st.caption(
    "Dica: use o perfil 'conservador' para sinais mais cautelosos e "
    "'agressivo' para sinais antecipados. Lotes sao referenciais para fracionar a venda da soja."
)
