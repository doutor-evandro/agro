# Agro Dashboard PRO - Versao Web (Streamlit)

Versao web do **Agro Dashboard PRO** (originalmente Tkinter desktop), agora acessivel via navegador e pronta para hospedagem em nuvem gratuita.

Reaproveita 100% da logica de negocio original (`core/`, `services/`, `data/`, `config/`) e substitui apenas a camada de UI por Streamlit.

---

## Estrutura

```
agro_dashboard_web/
├── app.py                   # Pagina inicial (Home)
├── requirements.txt         # Dependencias
├── .streamlit/config.toml   # Tema e configuracao Streamlit
├── pages/
│   ├── 1_Dashboard.py       # KPIs ao vivo + historico + analise tendencia soja
│   ├── 2_Analise.py         # Analise estatistica + semaforo + relatorio
│   ├── 3_Simulador_CDI.py   # Simulador de carry (vender hoje + CDI vs esperar)
│   └── 4_TradingView.py     # Graficos TradingView integrados
├── core/                    # (reaproveitado) calc, decision, stat_analysis, carry_simulator...
├── services/                # (reaproveitado) fetch_service, scheduler
├── data/                    # (reaproveitado) providers + storage (sqlite + json)
└── config/                  # (reaproveitado) settings
```

---

## Rodar localmente (Windows)

1. Abra o terminal na pasta do projeto:
   ```
   cd C:\Python\AgroDashboardPro\web\agro_dashboard_web
   ```

2. (Opcional) Crie um ambiente virtual:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale as dependencias:
   ```
   pip install -r requirements.txt
   ```

4. Rode a aplicacao:
   ```
   streamlit run app.py
   ```

5. O navegador abre em `http://localhost:8501`. Multiplos usuarios na mesma rede podem acessar pela URL `http://SEU_IP:8501`.

---

## Hospedar gratuitamente (Streamlit Community Cloud)

A maneira mais simples - 0 reais por mes, URL publica do tipo `https://agro-dashboard-pro.streamlit.app`.

1. **Crie um repositorio no GitHub** com o conteudo desta pasta (`agro_dashboard_web/`).
2. Acesse [https://share.streamlit.io](https://share.streamlit.io) e faca login com sua conta GitHub.
3. Clique em **New app**:
   - **Repository:** seu repositorio
   - **Branch:** main
   - **Main file path:** `app.py`
4. Clique em **Deploy**. A primeira build demora ~2 minutos.
5. Pronto! Compartilhe a URL com os usuarios.

### Observacoes para producao

- **Persistencia de dados:** o disco do Streamlit Cloud e efemero (reseta a cada deploy). Para historico permanente, considere:
  - Manter o `agro_history.json` versionado no repo (atualizado por GitHub Actions, por exemplo).
  - Usar um banco externo (Supabase, Neon, MongoDB Atlas - todos com tier gratuito).
- **Autenticacao** (opcional): use `st.secrets` ou um login simples com `streamlit-authenticator`.
- **Cache de cotacoes:** o `services/fetch_service.py` faz scraping a cada chamada. Considere envolver com `@st.cache_data(ttl=900)` para cachear por 15 minutos e reduzir requisicoes.

---

## Outras opcoes de hospedagem

- **Render** (free tier) - bom para apps com persistencia em volume.
- **Railway** ($5/mes apos free trial) - facil deploy e bom para cron jobs.
- **Fly.io** (free tier) - escalavel, requer Dockerfile.
- **PythonAnywhere** (free tier) - simples, mas Streamlit precisa de tier pago.

---

## Diferencas em relacao a versao desktop

- **Multi-usuario:** cada acesso e uma sessao independente.
- **TradingView:** carregado via iframe oficial (sem `pywebview`).
- **Exportacoes:** PDFs/TXT virou `st.download_button` (download via navegador, sem `filedialog`).
- **Auto-refresh:** toggle simples com meta refresh (em vez de scheduler em background). Para refresh real em background com cache compartilhado, use `@st.cache_data(ttl=...)` no fetch.

---

## Suporte

Se o widget do TradingView nao carregar, e provavel que o servidor de hospedagem esteja bloqueando scripts externos. Use uma plataforma que permita CSP customizado (Streamlit Cloud permite por padrao).
