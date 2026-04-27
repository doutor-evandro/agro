from pathlib import Path
import sys

APP_TITLE = "Agro Dashboard PRO"


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))


def _bundled_data_dir() -> Path:
    """
    Location where PyInstaller stores bundled data:
    - onefile: sys._MEIPASS
    - onedir:  <exe_dir>\\_internal
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
    Keep user data in a persistent folder when running as a PyInstaller executable.
    In source mode, keep existing behavior (project root).
    """
    if _is_frozen_app():
        # In onefile builds, `sys.executable` may point to the unpacked temp runtime.
        # `sys.argv[0]` keeps the real launcher path chosen by the user.
        exe_dir = Path(sys.argv[0]).resolve().parent

        # Dev-friendly fallback only for onefile builds that sit directly in `dist`.
        # For onedir builds, always keep data beside that executable folder.
        if exe_dir.name.lower() == "dist":
            repo_data_dir = exe_dir.parent / "AgroDashboardPro"
            if (repo_data_dir / "agro_history.json").exists() or (repo_data_dir / "agro_quotes.sqlite").exists():
                return repo_data_dir

        return exe_dir
    return Path(__file__).resolve().parent.parent


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
