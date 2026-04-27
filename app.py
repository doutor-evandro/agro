"""
Agro Dashboard PRO - Versao Web (Streamlit)
Pagina inicial / Home.
"""
from __future__ import annotations

import streamlit as st

from config.settings import APP_TITLE
from data.storage.json_store import init_json_store, series_history
from data.storage.sqlite_store import init_db


# Inicializa storage uma unica vez por sessao
@st.cache_resource(show_spinner=False)
def _bootstrap_storage():
    init_db()
    init_json_store()
    return True


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _bootstrap_storage()

    st.title(APP_TITLE)
    st.caption(
        "Painel profissional de mercado: monitoramento, analise estatistica e simulacao de decisao."
    )

    st.markdown(
        """
        ### Bem-vindo

        Use o menu lateral para navegar entre as secoes do painel:

        - **Dashboard** - cotacoes em tempo real (Soja B3, Milho B3, USD/BRL) e historico.
        - **Analise** - analise estatistica multivariada, semaforo de decisao e relatorio.
        - **Simulador CDI** - simulador de carry comparando vender hoje + CDI vs. esperar.
        - **TradingView** - graficos integrados (CCM1!, SJC1!, USD/BRL).
        """
    )

    points = series_history()
    n = len(points)
    if n > 0:
        last_ts = points[-1][0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Pontos no historico", f"{n}")
        col2.metric("Ultimo registro", last_ts.strftime("%Y-%m-%d %H:%M"))
        col3.metric("Sojas (US$/sc)", f"{points[-1][2]:.2f}")
    else:
        st.info(
            "Banco de historico vazio. Acesse a pagina **Dashboard** e clique em "
            "'Atualizar agora' para baixar a primeira cotacao."
        )

    st.divider()
    st.caption(
        "Fontes: Noticias Agricolas (B3) + AwesomeAPI (USD/BRL). "
        "Para deploy gratuito, veja o README.md."
    )


if __name__ == "__main__":
    main()
