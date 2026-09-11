"""
Baixa a ETTJ (Estrutura a Termo das Taxas de Juros) da ANBIMA para uma data.

Fonte: https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp
       ?Escolha=1&saida=csv&Idioma=PT&Dt_Ref=DD/MM/AAAA

Devolve um CSV (latin-1, separador ";", decimal ",") com:
  - parametros Svensson das curvas PREFIXADOS e IPCA (Beta 1..4, Lambda 1..2)
  - tabela "ETTJ PREF" por vertice (dias uteis) de ~1 a ~10 anos
  - tabela "PREFIXADOS (CIRCULAR 3.361)" com o trecho curto (21..126 dias uteis)

Guardamos os parametros Svensson (curva inteira, exata em qualquer prazo) + as
tabelas publicadas para conferencia. A ANBIMA so mantem poucas semanas on-line,
por isso este coletor roda todo dia e arquiva cada pregao (ver update.py).
"""
from __future__ import annotations

import datetime as dt
import time

import requests

URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/html",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class NoDataForDate(Exception):
    """A ANBIMA respondeu vazio: nao ha ETTJ para essa data (fim de semana, feriado, pregao ainda nao publicado)."""


def _ptbr_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s or s in {"-", "--"}:
        return None
    # pt-BR: "1.008" -> 1008 ; "13,4944" -> 13.4944 ; "7,59E-03" -> 7.59E-03
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse(csv_text: str, date: dt.date) -> dict:
    lines = [ln.rstrip("\r") for ln in csv_text.split("\n")]

    svensson: dict[str, dict] = {}
    vertices_pref: list[list[float]] = []
    short_pref: list[list[float]] = []
    section = None
    pending_circular = False

    for ln in lines:
        cells = ln.split(";")
        tag = cells[0].strip()

        if tag in ("PREFIXADOS", "IPCA") and len(cells) >= 7:
            key = "svensson_pref" if tag == "PREFIXADOS" else "svensson_ipca"
            b1, b2, b3, b4, l1, l2 = (_ptbr_float(c) for c in cells[1:7])
            if None not in (b1, b2, b3, b4, l1, l2):
                svensson[key] = {"b1": b1, "b2": b2, "b3": b3, "b4": b4, "l1": l1, "l2": l2}
            continue

        if tag.startswith("PREFIXADOS (CIRCULAR"):
            pending_circular = True
            section = None
            continue
        if tag.startswith("Vertices"):
            if "ETTJ PREF" in ln:
                section = "ettj"
            elif pending_circular:
                section = "circular"
                pending_circular = False
            else:
                section = None
            continue
        if tag.startswith("Erro"):
            section = None
            continue

        if section == "ettj" and len(cells) >= 3:
            v = _ptbr_float(cells[0])
            pref = _ptbr_float(cells[2])  # coluna ETTJ PREF
            if v is not None and pref is not None:
                vertices_pref.append([v, pref])
        elif section == "circular" and len(cells) >= 2:
            v = _ptbr_float(cells[0])
            taxa = _ptbr_float(cells[1])
            if v is not None and taxa is not None:
                short_pref.append([v, taxa])

    if "svensson_pref" not in svensson:
        raise NoDataForDate(date.isoformat())

    out = {
        "date": date.isoformat(),
        "source": "anbima-ettj",
        "fetched_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "vertices_pref": vertices_pref,
        "short_pref": short_pref,
    }
    out.update(svensson)
    return out


def fetch_ettj(date: dt.date, *, retries: int = 3, pause: float = 3.0) -> dict:
    params = {
        "Escolha": "1",
        "saida": "csv",
        "Idioma": "PT",
        "Dt_Ref": date.strftime("%d/%m/%Y"),
    }
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(URL, params=params, headers=HEADERS, timeout=45)
            resp.raise_for_status()
            resp.encoding = "latin-1"
            text = resp.text
            if not text.strip():
                raise NoDataForDate(date.isoformat())
            return _parse(text, date)
        except NoDataForDate:
            raise
        except requests.RequestException as err:
            last_err = err
            if attempt < retries:
                time.sleep(pause * attempt)
    raise RuntimeError(f"falha ao baixar {date.isoformat()}: {last_err!r}")


if __name__ == "__main__":  # teste manual: python collector/fetch_anbima.py 2026-09-10
    import json
    import sys

    d = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    try:
        print(json.dumps(fetch_ettj(d), indent=2, ensure_ascii=False))
    except NoDataForDate:
        print(f"sem ETTJ para {d}")
