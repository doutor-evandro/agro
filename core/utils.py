from __future__ import annotations
import re
from datetime import datetime
from typing import Optional


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_float_br(text: str) -> float:
    t = text.strip().replace(".", "").replace(",", ".")
    return float(t)


def safe_float_br(text: str) -> Optional[float]:
    try:
        return parse_float_br(text)
    except Exception:
        return None


def extract_date_ddmmyyyy(text: str) -> Optional[str]:
    m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    return m.group(1) if m else None


def fmt_money_pt(x: float) -> str:
    # 1234.56 -> "1.234,56"
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct_pt(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return f"{x:.2f}%"
