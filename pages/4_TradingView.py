"""
Pagina TradingView - graficos integrados via widget oficial do TradingView.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="TradingView", layout="wide")
st.title("TradingView - Agro Charts")
st.caption("Graficos: CCM1! (Milho B3), SJC1! (Soja B3) e USD/BRL.")

SYMBOLS = {
    "MILHO B3 (CCM1!)": "BMFBOVESPA:CCM1!",
    "SOJA B3 (SJC1!)": "BMFBOVESPA:SJC1!",
    "USD / BRL": "FX_IDC:USDBRL",
}


def _widget_html(symbol: str, container_id: str, height: int = 520) -> str:
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{ margin:0; padding:0; height:100%; background:#fff; font-family: Arial, sans-serif; }}
    .box {{ height: {height}px; border:1px solid #e5e5e5; border-radius:10px; overflow:hidden; }}
  </style>
</head>
<body>
  <div class="box" id="{container_id}"></div>
  <script src="https://s3.tradingview.com/tv.js"></script>
  <script>
    new TradingView.widget({{
      "autosize": true,
      "symbol": "{symbol}",
      "interval": "15",
      "timezone": "America/Sao_Paulo",
      "theme": "light",
      "style": "1",
      "locale": "br",
      "toolbar_bg": "#f1f3f6",
      "enable_publishing": false,
      "hide_top_toolbar": false,
      "hide_legend": false,
      "save_image": true,
      "container_id": "{container_id}"
    }});
  </script>
</body>
</html>
"""


tab_labels = list(SYMBOLS.keys())
tabs = st.tabs(tab_labels)

for i, label in enumerate(tab_labels):
    with tabs[i]:
        symbol = SYMBOLS[label]
        components.html(_widget_html(symbol, f"tv_{i}", 540), height=560, scrolling=False)

st.divider()
st.caption(
    "Os widgets sao carregados diretamente do TradingView (s3.tradingview.com/tv.js) "
    "via iframe. Se ficar em branco, verifique se o navegador nao esta bloqueando "
    "scripts de terceiros."
)
