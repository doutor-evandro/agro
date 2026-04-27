"""
Pagina Dashboard - cotacoes ao vivo + historico + analise de tendencia da soja.
"""
from __future__ import annotations
 
from datetime import datetime, timedelta
import io
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st
 
from core.decision import analysis_to_text, analyze_soy_trend, select_window_points
from core.utils import fmt_money_pt, fmt_pct_pt
from data.storage.json_store import append_snapshot, init_json_store, series_history
from data.storage.sqlite_store import init_db, insert_snapshot, last_snapshot
from services.fetch_service import fetch_snapshot
 
 
@st.cache_resource(show_spinner=False)
def _bootstrap():
    init_db()
    init_json_store()
    return True
 
 
# Cache compartilhado entre todos os usuarios da app: ttl=900s (15 min).
# Reduz drasticamente o numero de chamadas a AwesomeAPI / Noticias Agricolas
# evitando o erro 429 (rate limit) e melhora o tempo de resposta.
@st.cache_data(ttl=900, show_spinner=False)
def fetch_snapshot_cached():
    return fetch_snapshot()
 
 
_bootstrap()
st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Dashboard")
st.caption("Cotacoes em tempo real (Soja, Milho, USD/BRL) e historico.")
 
# ---------- Top bar ----------
col_a, col_b, col_c = st.columns([1, 1, 4])
with col_a:
    if st.button("Atualizar agora", type="primary", use_container_width=True):
        with st.spinner("Buscando cotacoes..."):
            try:
                snap = fetch_snapshot_cached()
                insert_snapshot(snap)
                append_snapshot(snap)
                st.session_state["last_snapshot_ts"] = snap.ts
                st.success(f"Atualizado: {snap.ts}")
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Too Many Requests" in msg:
                    st.error(
                        "Limite de requisicoes atingido na fonte de cotacoes (erro 429). "
                        "Aguarde alguns minutos e tente novamente. "
                        "O cache de 15 min reduz esse problema apos a primeira atualizacao bem-sucedida."
                    )
                else:
                    st.error(f"Falha na atualizacao: {msg}")
 
    # Botao para limpar cache manualmente, se o usuario quiser forcar nova busca
    if st.button("Limpar cache", help="Forca nova consulta as fontes na proxima atualizacao", use_container_width=True):
        fetch_snapshot_cached.clear()
        st.success("Cache limpo.")
 
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
 
# ---------- Grafico historico ----------
st.subheader("Historico")
 
points = series_history()
 
range_options = {
    "7 dias": 7,
    "30 dias": 30,
    "90 dias": 90,
    "180 dias": 180,
    "1 ano": 365,
    "Tudo": None,
}
sel = st.radio("Periodo", list(range_options.keys()), index=2, horizontal=True)
days = range_options[sel]
 
filtered = points
if days is not None:
    cutoff = datetime.now() - timedelta(days=days)
    filtered = [p for p in points if p[0] >= cutoff]
 
if not filtered:
    st.warning("Nao ha pontos no periodo selecionado.")
else:
    ts = [p[0] for p in filtered]
    soja_brl = [p[4] for p in filtered]
    milho = [p[1] for p in filtered]
 
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(ts, soja_brl, label="Soja (R$/sc)", color="#2e7d32", linewidth=1.8)
    ax.plot(ts, milho, label="Milho (R$/sc)", color="#ef6c00", linewidth=1.4, alpha=0.85)
    ax.set_ylabel("R$ por saca")
    ax.set_title(f"Cotacoes em R$/sc - {sel}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.autofmt_xdate()
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
