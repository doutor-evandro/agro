"""
Pagina Simulador CDI - compara vender hoje + CDI vs. esperar 3/6/9 meses.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core.carry_simulator import (
    HORIZONS,
    minimum_future_price_scenarios,
    simulate_scenarios,
    summarize_recommendation,
)
from data.storage.json_store import init_json_store, series_history
from data.storage.sqlite_store import init_db, last_snapshot


@st.cache_resource(show_spinner=False)
def _bootstrap():
    init_db()
    init_json_store()
    return True


_bootstrap()
st.set_page_config(page_title="Simulador CDI", layout="wide")
st.title("Simulador de Carry (CDI)")
st.caption(
    "Compara o resultado de vender hoje e aplicar no CDI com o resultado de "
    "esperar 3/6/9 meses, considerando descontos (capital, funrural, risco)."
)

# ---------- Defaults a partir do ultimo snapshot ----------
last = last_snapshot()
default_soja = float(last.soja_brl) if last else 130.0
default_milho = float(last.milho.price) if last else 70.0

# ---------- Inputs ----------
mode = st.radio(
    "Selecao do ativo",
    ("SOJA + MILHO", "Apenas SOJA", "Apenas MILHO"),
    horizontal=True,
)

with st.expander("Valores hoje e quantidade", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        soja_today = st.number_input("Soja hoje (R$/sc)", min_value=0.0, value=round(default_soja, 2), step=0.5)
    with c2:
        soja_sacks = st.number_input("Sacas soja", min_value=0.0, value=1000.0, step=100.0)
    with c3:
        milho_today = st.number_input("Milho hoje (R$/sc)", min_value=0.0, value=round(default_milho, 2), step=0.5)
    with c4:
        milho_sacks = st.number_input("Sacas milho", min_value=0.0, value=1000.0, step=100.0)

with st.expander("Preco esperado de venda futura (R$/sc)", expanded=True):
    futs_soja, futs_milho = {}, {}
    cols = st.columns(len(HORIZONS) * 2)
    for j, m in enumerate(HORIZONS):
        with cols[j]:
            futs_soja[m] = st.number_input(f"Soja {m}m", min_value=0.0, value=round(default_soja * (1 + 0.03 * j), 2), step=0.5, key=f"fs_{m}")
        with cols[len(HORIZONS) + j]:
            futs_milho[m] = st.number_input(f"Milho {m}m", min_value=0.0, value=round(default_milho * (1 + 0.03 * j), 2), step=0.5, key=f"fm_{m}")

with st.expander("Rendimento (CDI)"):
    c1, c2 = st.columns(2)
    with c1:
        cdi_monthly = st.number_input("CDI mensal liquido (% a.m.)", min_value=0.0, value=1.00, step=0.05, format="%.2f")
    with c2:
        cdi_annual_calc = ((1.0 + cdi_monthly / 100.0) ** 12 - 1.0) * 100.0
        st.metric("CDI anual equivalente", f"{cdi_annual_calc:.2f}%")

with st.expander("Descontos"):
    c1, c2, c3 = st.columns(3)
    with c1:
        capital = st.slider("Capital (%)", 0.0, 2.0, 1.0, 0.5)
    with c2:
        funrural = st.slider("Funrural (%)", 0.0, 3.0, 1.5, 0.5)
    with c3:
        risk = st.number_input("Desconto de risco no futuro (%)", min_value=0.0, value=0.0, step=0.5, format="%.2f")

run = st.button("Simular", type="primary")

# ---------- Simulacao ----------
def _show_block(commodity: str, scenarios, sacks: float, price_today: float):
    st.subheader(f"{commodity}")
    if not scenarios:
        st.warning(f"Sem cenarios validos para {commodity}.")
        return

    rec = summarize_recommendation(scenarios)
    st.markdown(f"**Recomendacao:** {rec}")

    rows = []
    for s in scenarios:
        rows.append(
            {
                "Prazo": f"{s.months}m",
                "Sacas": f"{s.sacks:,.0f}",
                "Receber hoje (liq)": f"R$ {s.receipt_today_total:,.2f}",
                "Hoje + CDI no prazo": f"R$ {s.fv_sell_now_cdi_total:,.2f}",
                "Esperar (no prazo)": f"R$ {s.sell_future_total:,.2f}",
                "Preco indif. futuro": f"R$ {s.breakeven_future_price_input:,.2f}",
                "Diferenca": f"R$ {s.diff_total:+,.2f}  ({s.diff_pct:+.2f}%)",
                "Decisao": s.decision,
            }
        )
    df = pd.DataFrame(rows)

    def _color(row):
        if row["Decisao"] == "VENDER HOJE":
            return ["background-color: #e8f5e9"] * len(row)
        return ["background-color: #fff3e0"] * len(row)

    st.dataframe(df.style.apply(_color, axis=1), use_container_width=True, hide_index=True)

    # Grafico
    months = [f"{s.months}m" for s in scenarios]
    cdi_vals = [s.fv_sell_now_cdi_total for s in scenarios]
    fut_vals = [s.sell_future_total for s in scenarios]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = range(len(months))
    bw = 0.35
    ax.bar([i - bw / 2 for i in x], cdi_vals, width=bw, label="Hoje + CDI", color="#1565c0")
    ax.bar([i + bw / 2 for i in x], fut_vals, width=bw, label="Esperar", color="#ef6c00")
    ax.set_xticks(list(x))
    ax.set_xticklabels(months)
    ax.set_ylabel("R$ (valor total)")
    ax.set_title(f"{commodity} - Comparativo de cenarios")
    ax.grid(True, alpha=0.25, axis="y")
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)


if run or "sim_done" in st.session_state:
    st.session_state["sim_done"] = True

    if mode in ("SOJA + MILHO", "Apenas SOJA"):
        sojas = simulate_scenarios(
            "SOJA",
            soja_today,
            cdi_monthly,
            futs_soja,
            sacks=soja_sacks,
            capital_discount_pct=capital,
            funrural_discount_pct=funrural,
            risk_discount_total_pct=risk,
        )
        _show_block("SOJA", sojas, soja_sacks, soja_today)

    if mode in ("SOJA + MILHO", "Apenas MILHO"):
        milhos = simulate_scenarios(
            "MILHO",
            milho_today,
            cdi_monthly,
            futs_milho,
            sacks=milho_sacks,
            capital_discount_pct=capital,
            funrural_discount_pct=funrural,
            risk_discount_total_pct=risk,
        )
        _show_block("MILHO", milhos, milho_sacks, milho_today)

    # Cenario 2 - Preco minimo (so para soja por padrao)
    st.subheader("Cenario 2 - Preco Futuro Minimo (Soja)")
    floors = minimum_future_price_scenarios(
        "SOJA",
        soja_today,
        cdi_monthly,
        sacks=soja_sacks,
        capital_discount_pct=capital,
        funrural_discount_pct=funrural,
        risk_discount_total_pct=risk,
    )
    if floors:
        rows = []
        for s in floors:
            rows.append(
                {
                    "Prazo": f"{s.months}m",
                    "Preco minimo (R$/sc)": f"R$ {s.min_future_price_input:,.2f}",
                    "Alta minima vs hoje": f"{s.pct_up_vs_today_input:+.2f}%",
                    "Hoje + CDI ref. (total)": f"R$ {s.fv_sell_now_cdi_total:,.2f}",
                    "Preco hoje informado": f"R$ {s.price_today_input:,.2f}",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Interpretacao: para vender no futuro, o preco bruto (R$/sc) precisa "
            "atingir pelo menos o valor 'Preco minimo' para igualar o resultado de "
            "vender hoje + CDI."
        )
else:
    st.info("Configure os parametros acima e clique em 'Simular'.")
