from pathlib import Path
import os
import sys
 
APP_TITLE = "Agro Dashboard PRO"
 
 
def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))
 
 
def _bundled_data_dir() -> Path:
    """
    Diretorio (somente leitura) onde ficam os dados do projeto/repo.
    - PyInstaller onefile: sys._MEIPASS
    - PyInstaller onedir:  <exe_dir>/_internal
    - Modo source (cloud/local): raiz do projeto
    """
    if not _is_frozen_app():
        return Path(__file__).resolve().parent.parent
 
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
 
    exe_dir = Path(sys.executable).resolve().parent
    internal_dir = exe_dir / "_internal"
    if internal_dir.exists():
        return internal_dir
    return exe_dir
 
 
def _runtime_data_dir() -> Path:
    """
    Diretorio gravavel onde a app armazena dados em runtime (banco SQLite,
    JSON de historico, estado do simulador).
 
    Ordem de prioridade:
      1) Variavel de ambiente AGRO_DATA_DIR (override explicito)
      2) Modo PyInstaller (executavel desktop): pasta do executavel
      3) Modo source rodando no Streamlit Cloud / Linux server: ~/.agro_dashboard
         (sempre gravavel, nao depende de o repo ser ou nao read-only)
      4) Modo source rodando localmente (Windows desktop): raiz do projeto
         (mantem comportamento original para uso offline)
    """
    # 1) override explicito
    env_dir = os.environ.get("AGRO_DATA_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
 
    # 2) PyInstaller
    if _is_frozen_app():
        exe_dir = Path(sys.argv[0]).resolve().parent
        if exe_dir.name.lower() == "dist":
            repo_data_dir = exe_dir.parent / "AgroDashboardPro"
            if (repo_data_dir / "agro_history.json").exists() or (repo_data_dir / "agro_quotes.sqlite").exists():
                return repo_data_dir
        return exe_dir
 
    # 3) Cloud / Linux: usa pasta home (gravavel)
    project_root = Path(__file__).resolve().parent.parent
    is_streamlit_cloud = "/mount/src/" in str(project_root) or os.environ.get("STREAMLIT_RUNTIME_ENV") is not None
    is_linux_server = sys.platform.startswith("linux") and not _path_is_writable(project_root)
 
    if is_streamlit_cloud or is_linux_server:
        home_dir = Path.home() / ".agro_dashboard"
        home_dir.mkdir(parents=True, exist_ok=True)
        return home_dir
 
    # 4) Local (Windows desktop, dev local): raiz do projeto
    return project_root
 
 
def _path_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".__write_probe__"
        probe.write_text("ok")
        probe.unlink()
        return True
    except Exception:
        return False
 
 
APP_DIR = _runtime_data_dir()
BUNDLED_DATA_DIR = _bundled_data_dir()
DB_PATH = APP_DIR / "agro_quotes.sqlite"
JSON_DB_PATH = APP_DIR / "agro_history.json"
CDI_SIM_STATE_PATH = APP_DIR / "cdi_simulator_state.json"
BUNDLED_DB_PATH = BUNDLED_DATA_DIR / "agro_quotes.sqlite"
BUNDLED_JSON_DB_PATH = BUNDLED_DATA_DIR / "agro_history.json"
BUNDLED_CDI_SIM_STATE_PATH = BUNDLED_DATA_DIR / "cdi_simulator_state.json"
 
# Fontes
NA_URLS = {
    "MILHO": "https://www.noticiasagricolas.com.br/cotacoes/milho/milho-b3-prego-regular",
    "SOJA":  "https://www.noticiasagricolas.com.br/cotacoes/soja/soja-b3-pregao-regular",
}
 
FX_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
 
USER_AGENT = {"User-Agent": "Mozilla/5.0"}
 
# Default update interval
DEFAULT_INTERVAL_SEC = 900  # 15 min
MIN_INTERVAL_SEC = 30
