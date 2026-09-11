"""
Baixa e faz o parse da curva de juros PRE (DI x Pre) da B3.

Fonte: https://www2.bmf.com.br/pages/portal/bmfbovespa/lumis/lum-taxas-referenciais-bmf-ptBR.asp
       parametros Data=DD/MM/AAAA, Data1=AAAAMMDD, slcTaxa=PRE
Mesma pagina usada pelo pacote R `rb3` (ropensci) para a funcao yc_get.

A B3 mantem ~1 mes de historico on-line -- por isso este coletor roda todo dia
e arquiva cada pregao (ver update.py).
"""
from __future__ import annotations

import datetime as dt
import io
import time

import pandas as pd
import requests

URL = "https://www2.bmf.com.br/pages/portal/bmfbovespa/lumis/lum-taxas-referenciais-bmf-ptBR.asp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# frases que a B3 devolve quando nao ha dado para a data (fim de semana, feriado,
# pregao ainda nao fechado)
_NO_DATA_MARKERS = (
    "nao foi possivel",
    "não foi possível",
    "nao ha dados",
    "não há dados",
    "nenhum registro",
)


class NoDataForDate(Exception):
    """A B3 respondeu, mas nao ha curva para essa data."""


def _looks_empty(html: str) -> bool:
    low = html.lower()
    return any(m in low for m in _NO_DATA_MARKERS)


def fetch_pre_curve(date: dt.date, *, retries: int = 3, pause: float = 3.0) -> dict:
    """
    Devolve um dump fiel da tabela PRE para `date`:

        {
          "date": "2026-09-10",
          "source": "b3-lum-taxas-referenciais-PRE",
          "fetched_at": "2026-09-10T22:07:03Z",
          "columns": ["term_days", "rate_252", "rate_360"],
          "rows": [[1, 14.9, 14.68], [2, 14.9, 14.68], ...]
        }

    Levanta NoDataForDate se a B3 nao tem curva para a data.
    """
    params = {
        "Data": date.strftime("%d/%m/%Y"),
        "Data1": date.strftime("%Y%m%d"),
        "slcTaxa": "PRE",
    }

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(URL, params=params, headers=HEADERS, timeout=40)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "latin-1"
            html = resp.text

            if _looks_empty(html):
                raise NoDataForDate(date.isoformat())

            table = _pick_curve_table(html)
            if table is None or table.empty:
                raise NoDataForDate(date.isoformat())

            rows = [[_num(v) for v in rec] for rec in table.itertuples(index=False)]
            rows = [r for r in rows if r and r[0] is not None]
            if not rows:
                raise NoDataForDate(date.isoformat())

            return {
                "date": date.isoformat(),
                "source": "b3-lum-taxas-referenciais-PRE",
                "fetched_at": dt.datetime.now(dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "columns": ["term_days", "rate_252", "rate_360"][: len(rows[0])],
                "rows": rows,
            }
        except NoDataForDate:
            raise
        except (requests.RequestException, ValueError) as err:  # rede / parse
            last_err = err
            if attempt < retries:
                time.sleep(pause * attempt)

    raise RuntimeError(f"falha ao baixar {date.isoformat()}: {last_err!r}")


def _pick_curve_table(html: str) -> pd.DataFrame | None:
    """Escolhe, entre as tabelas da pagina, a que tem a curva (coluna de prazo + taxas)."""
    try:
        tables = pd.read_html(io.StringIO(html), decimal=",", thousands=".")
    except ValueError:
        return None

    best: pd.DataFrame | None = None
    for tb in tables:
        # achata cabecalho multi-nivel, se houver
        tb = tb.copy()
        tb.columns = [str(c).strip().lower() for c in range(len(tb.columns))]
        if tb.shape[1] < 2 or len(tb) < 5:
            continue
        # a coluna de prazo (dias) deve ser inteira e crescente
        col0 = pd.to_numeric(tb.iloc[:, 0], errors="coerce")
        if col0.notna().sum() < 5:
            continue
        if not col0.dropna().is_monotonic_increasing:
            continue
        if best is None or len(tb) > len(best):
            best = tb
    return best


def _num(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    s = str(value).strip().replace(".", "").replace(",", ".")
    if not s or s in {"-", "--"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


if __name__ == "__main__":  # teste manual: python collector/fetch_b3.py 2026-09-10
    import json
    import sys

    d = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    try:
        print(json.dumps(fetch_pre_curve(d), indent=2, ensure_ascii=False))
    except NoDataForDate:
        print(f"sem dado para {d}")
