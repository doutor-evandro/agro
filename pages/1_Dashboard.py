"""
Pagina Dashboard - cotacoes ao vivo + historico + analise de tendencia da soja.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from core.decision import analysis_to_text, analyze_soy_trend, select_window_points
from core.utils import fmt_money_pt, fmt_pct_pt
from data.storage.json_store import append_snapshot, init_json_store, series_history
from data.storage.sqlite_store import init_db, insert_snapshot, last_snapshot
from services.fetch_service import fetch_snapshot

# Faixas temporais iguais ao HistoryChart do app desktop (AgroDashboardPro/ui/charts/history_chart.py).
_RANGE_UI = [
    ("1 dia", "1D"),
    ("5 dias", "5D"),
    ("1 mes", "1M"),
    ("6 meses", "6M"),
    ("1 ano", "1Y"),
    ("2 anos", "2Y"),
    ("Todos", "ALL"),
]


def _history_range_cutoff(range_key: str) -> datetime | None:
    now = datetime.now()
    if range_key == "1D":
        return now - timedelta(days=1)
    if range_key == "5D":
        return now - timedelta(days=5)
    if range_key == "1M":
        return now - timedelta(days=30)
    if range_key == "6M":
        return now - timedelta(days=182)
    if range_key == "1Y":
        return now - timedelta(days=365)
    if range_key == "2Y":
        return now - timedelta(days=730)
    if range_key == "ALL":
        return None
    return now - timedelta(days=730)


def _filter_points_by_range(points, range_key: str):
    cutoff = _history_range_cutoff(range_key)
    if cutoff is None:
        return list(points)
    return [p for p in points if p[0] >= cutoff]


# Deve ser o primeiro comando Streamlit desta pagina (antes de cache/bootstrap).
st.set_page_config(page_title="Dashboard", layout="wide")


@st.cache_resource(show_spinner=False)
def _bootstrap():
    init_db()
    init_json_store()
    return True


_bootstrap()
st.title("Dashboard")
st.caption("Cotacoes em tempo real (Soja, Milho, USD/BRL) e historico.")

# ---------- Top bar ----------
col_a, col_b, col_c = st.columns([1, 1, 4])
with col_a:
    if st.button("Atualizar agora", type="primary", use_container_width=True):
        with st.spinner("Buscando cotacoes..."):
            try:
                # Busca sempre ao vivo (sem @st.cache_data): cache compartilhado
                # fazia o botao devolver cotacao antiga ate expirar o TTL.
                snap = fetch_snapshot()
                insert_snapshot(snap)
                append_snapshot(snap)
                st.session_state["last_snapshot_ts"] = snap.ts
                st.success(f"Atualizado: {snap.ts}")
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Too Many Requests" in msg:
                    st.error(
                        "Limite de requisicoes atingido na fonte de cotacoes (erro 429). "
                        "Aguarde alguns minutos e tente novamente."
                    )
                else:
                    st.error(f"Falha na atualizacao: {msg}")

with col_b:
    auto = st.toggle("Auto-refresh (60s)", value=False, help="Recarrega a pagina a cada 60s")
    if auto:
        # Streamlit nativo: meta refresh
        st.markdown(
            "<meta http-equiv='refresh' content='60'>",
            unsafe_allow_html=True,
        )

# ---------- KPIs (ultimo snapshot) ----------
s = last_snapshot()

st.subheader("Cotacoes (ultimo snapshot)")

if s is None:
    st.info("Nenhum snapshot armazenado ainda. Clique em 'Atualizar agora'.")
else:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        label=f"MILHO ({s.milho.contract_label})",
        value=f"R$ {fmt_money_pt(s.milho.price)} /sc",
        delta=fmt_pct_pt(s.milho.change_pct) if s.milho.change_pct is not None else None,
    )
    k2.metric(
        label=f"SOJA ({s.soja.contract_label})",
        value=f"US$ {fmt_money_pt(s.soja.price)} /sc",
        delta=fmt_pct_pt(s.soja.change_pct) if s.soja.change_pct is not None else None,
    )
    k3.metric(
        label="USD / BRL",
        value=f"R$ {fmt_money_pt(s.fx.usd_brl)}",
        delta=None,
    )
    k4.metric(
        label="SOJA em R$",
        value=f"R$ {fmt_money_pt(s.soja_brl)} /sc",
        delta=None,
        help=f"Base: US$ {fmt_money_pt(s.soja.price)} x R$ {fmt_money_pt(s.fx.usd_brl)}",
    )
    st.caption(f"Atualizado em {s.ts}  |  Fonte: {s.source}")

# ---------- Graficos historicos (espelho do desktop: 3 linhas = milho | soja US$+R$ | USD/BRL) ----------
st.subheader("Historico")
st.caption(
    "Mesmas faixas do programa desktop (1 dia … 2 anos … Todos). "
    "Tres graficos: milho em R$/sc; soja em US$/sc e em R$/sc (eixo direito); USD/BRL."
)

points = series_history()

labels_only = [x[0] for x in _RANGE_UI]
keys_by_label = dict(_RANGE_UI)
sel_label = st.radio(
    "Faixa",
    labels_only,
    index=5,
    horizontal=True,
    help="Equivalente aos botoes 'Faixa' do Agro Dashboard PRO desktop.",
)
range_key = keys_by_label[sel_label]

filtered = _filter_points_by_range(points, range_key)

if not filtered:
    st.warning("Nao ha pontos na faixa selecionada.")
else:
    x = [p[0] for p in filtered]
    milho_y = [p[1] for p in filtered]
    soja_usd_y = [p[2] for p in filtered]
    usd_brl_y = [p[3] for p in filtered]
    soja_brl_y = [p[4] for p in filtered]

    n_pts = len(filtered)
    mk = "o" if n_pts <= 24 else None
    ms = 4 if n_pts <= 24 else 0

    fig = plt.figure(figsize=(11, 10))
    fig.set_constrained_layout(True)
    ax_milho = fig.add_subplot(311)
    ax_soja = fig.add_subplot(312)
    ax_fx = fig.add_subplot(313)
    ax_soja_brl = ax_soja.twinx()

    ax_milho.set_title("Milho (R$/sc)")
    ax_soja.set_title("Soja (US$/sc e R$/sc)")
    ax_fx.set_title("USD/BRL")

    (lm,) = ax_milho.plot(x, milho_y, color="#2e7d32", linewidth=1.6, marker=mk, markersize=ms)
    (ls_usd,) = ax_soja.plot(x, soja_usd_y, color="#1565c0", linewidth=1.6, marker=mk, markersize=ms)
    (ls_brl,) = ax_soja_brl.plot(x, soja_brl_y, color="#ef6c00", linewidth=1.6, marker=mk, markersize=ms)
    (lf,) = ax_fx.plot(x, usd_brl_y, color="#6a1b9a", linewidth=1.6, marker=mk, markersize=ms)

    ax_milho.set_ylabel("R$/sc")
    ax_soja.set_ylabel("US$/sc")
    ax_soja_brl.set_ylabel("R$/sc")
    ax_fx.set_ylabel("R$/US$")

    ax_milho.grid(True, alpha=0.25)
    ax_soja.grid(True, alpha=0.25)
    ax_fx.grid(True, alpha=0.25)

    ax_milho.legend(handles=[lm], loc="upper left")
    ax_soja.legend(handles=[ls_usd, ls_brl], loc="upper left")
    ax_fx.legend(handles=[lf], loc="upper left")

    fig.suptitle(f"Historico — {sel_label}", fontsize=12, y=1.02)
    st.pyplot(fig, clear_figure=True)

# ---------- Analise de tendencia (Soja R$) ----------
st.subheader("Analise de Decisao - Soja R$ (janela 14 dias)")
analysis = analyze_soy_trend(points, window_days=14, min_points=5)
if analysis is None:
    st.info("Sem pontos suficientes para a analise (minimo 5 nos ultimos 14 dias).")
else:
    st.text(analysis_to_text(analysis))

# ---------- Exportar 2 semanas TXT ----------
st.subheader("Exportar")
selected, label = select_window_points(points, window_days=14, min_points=5)
if selected:
    a = analyze_soy_trend(points, window_days=14, min_points=5)
    lines = [
        "AGRO DASHBOARD PRO - EXPORTACAO",
        f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Janela utilizada: {label}",
        f"Pontos: {len(selected)}",
        "",
        "ANALISE DE TENDENCIA (SOJA R$/sc)",
        analysis_to_text(a) if a else "n/a",
        "",
        "DADOS",
        "data_hora;milho_rs_sc;soja_usd_sc;usd_brl;soja_rs_sc",
    ]
    for dt, m, su, fx, sb in selected:
        lines.append(f"{dt.strftime('%Y-%m-%d %H:%M:%S')};{m:.4f};{su:.4f};{fx:.4f};{sb:.4f}")
    txt = "\n".join(lines) + "\n"
    st.download_button(
        "Baixar TXT (ultimas 2 semanas)",
        data=txt.encode("utf-8"),
        file_name=f"agro_2_semanas_{datetime.now():%Y%m%d_%H%M%S}.txt",
        mime="text/plain",
    )
else:
    st.caption("Sem dados para exportar.")
