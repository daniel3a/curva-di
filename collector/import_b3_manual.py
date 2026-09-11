"""
Varre b3-manual-inbox/ atras de arquivos "Mercado de Derivativos - Taxas de
Mercado para Swaps" baixados manualmente da B3 (pagina "Pesquisa por pregao"),
e converte em arquivos que o dashboard consegue ler.

Formato do arquivo da B3 (CSV ";" , latin-1, decimal ","):
    Descricao da Taxa;Dias Uteis;Dias Corridos;Preco/Taxa
    DI x pre;1;1;13,90
    DI x pre;2;4;13,82
    ...

A data do pregao nao vem dentro do arquivo -- e extraida do NOME dele
(procura um AAAAMMDD, ex.: TaxaReferencia_PRE_20260910.csv -> 2026-09-10).
Reprocessar o mesmo arquivo e seguro (idempotente): so sobrescreve o
arquivo arquivado daquela data.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import re

from vertices import build_vertices

ROOT = pathlib.Path(__file__).resolve().parents[1]
INBOX = ROOT / "b3-manual-inbox"
RAW_DIR = ROOT / "docs" / "data" / "raw_b3"
CURVES_JSON = ROOT / "docs" / "data" / "curves_b3.json"

DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")

# mesma grade de vertices (por data de vencimento) usada na curva ANBIMA -- ver vertices.py
VERTICES = build_vertices()


def extract_date(filename: str) -> dt.date | None:
    m = DATE_RE.search(filename)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def parse_file(path: pathlib.Path) -> list[list[float]]:
    text = path.read_text(encoding="latin-1")
    rows: list[list[float]] = []
    reader = csv.reader(text.splitlines(), delimiter=";")
    next(reader, None)  # cabecalho
    for rec in reader:
        if len(rec) < 4:
            continue
        try:
            du = float(rec[1].strip())
            dc = float(rec[2].strip())
            taxa = float(rec[3].strip().replace(".", "").replace(",", "."))
        except (ValueError, IndexError):
            continue
        rows.append([du, dc, taxa])
    return rows


def import_inbox() -> int:
    """Le todo arquivo *.csv da inbox e arquiva em raw_b3/AAAA-MM-DD.json. Devolve quantos processou."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(INBOX.glob("*.csv")):
        date = extract_date(f.name)
        if not date:
            print(f"  ? {f.name}: nao achei AAAAMMDD no nome, pulando")
            continue
        rows = parse_file(f)
        if not rows:
            print(f"  ! {f.name}: nenhuma linha valida encontrada")
            continue
        out = RAW_DIR / f"{date.isoformat()}.json"
        out.write_text(
            json.dumps(
                {
                    "date": date.isoformat(),
                    "source": "b3-manual",
                    "source_file": f.name,
                    "vertices": rows,  # [dias_uteis, dias_corridos, taxa_pct]
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        n += 1
        print(f"  + {f.name} -> {date.isoformat()} ({len(rows)} vertices)")
    return n


def _interp(xs: list[float], ys: list[float], x: float) -> float | None:
    if not xs:
        return None
    if x <= xs[0]:
        return round(ys[0], 4) if x >= xs[0] * 0.5 else None
    if x >= xs[-1]:
        return None
    for i in range(1, len(xs)):
        if xs[i] >= x:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return round(ys[i - 1] + t * (ys[i] - ys[i - 1]), 4)
    return None


def _to_grid(vertices: list[list[float]], curve_date: dt.date) -> list[float | None]:
    """Interpola o arquivo bruto da B3 (dias corridos x taxa) em cada data de vencimento."""
    rows = sorted(vertices, key=lambda r: r[1])  # ordena por dias corridos
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    rates = []
    for _, vdate in VERTICES:
        dc = (vdate - curve_date).days
        rates.append(_interp(xs, ys, dc) if dc > 0 else None)
    return rates


def rebuild() -> int:
    """Reconstroi docs/data/curves_b3.json a partir de tudo que ja foi arquivado. Devolve o total."""
    files = sorted(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else []
    curves = []
    for p in files:
        raw = json.loads(p.read_text(encoding="utf-8"))
        curve_date = dt.date.fromisoformat(raw["date"])
        curves.append({"date": raw["date"], "rates": _to_grid(raw["vertices"], curve_date)})

    now = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    CURVES_JSON.write_text(
        json.dumps(
            {
                "generated_at": now,
                "source": "B3 - Mercado de Derivativos: Taxas de Mercado para Swaps (DI x pre) - importado manualmente",
                "method": "interpolacao linear em dias corridos sobre o arquivo publicado pela B3, avaliada em cada data de vencimento",
                "tenors": [{"label": lab, "date": vdate.isoformat()} for lab, vdate in VERTICES],
                "curves": curves,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return len(curves)


def run_and_rebuild() -> tuple[int, int]:
    INBOX.mkdir(parents=True, exist_ok=True)
    novos = import_inbox()
    total = rebuild()
    return novos, total


if __name__ == "__main__":
    novos, total = run_and_rebuild()
    print(f"novos: {novos} | total arquivado (B3 manual): {total}")
