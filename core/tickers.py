from __future__ import annotations
from datetime import date

MONTH_LETTER = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M", 7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}

def ticker_vigente(radical: str, ref_date: date | None = None) -> str:
    ref_date = ref_date or date.today()
    letter = MONTH_LETTER[ref_date.month]
    yy = str(ref_date.year)[-2:]
    return f"{radical}{letter}{yy}"
