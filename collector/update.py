"""
Roda todo dia (GitHub Actions). Faz:

  1. olha quais pregoes ja estao arquivados em docs/data/raw/
  2. tenta baixar da ANBIMA os pregoes ausentes dos ultimos N dias uteis
     (a ANBIMA so mantem poucas semanas on-line)
  3. grava o dump de cada pregao novo em docs/data/raw/AAAA-MM-DD.json
     (parametros Svensson + tabelas publicadas)
  4. reconstroi docs/data/curves.json (curva avaliada numa grade fixa de vertices,
     pela formula de Svensson) e docs/data/index.json

Nunca derruba o job por um dia sem dado ou instabilidade da fonte -- o proximo run
preenche o buraco. Rodar localmente: python collector/update.py
"""
from __future__ import annotations

import datetime as dt
import json
import math
import pathlib
import sys

from fetch_anbima import NoDataForDate, fetch_ettj
from import_b3_manual import run_and_rebuild as run_b3_manual

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "docs" / "data" / "raw"
CURVES_JSON = ROOT / "docs" / "data" / "curves.json"
INDEX_JSON = ROOT / "docs" / "data" / "index.json"

LOOKBACK_BIZ_DAYS = 45
MAX_CONSECUTIVE_MISSES = 12

# grade fixa de vertices para o dashboard: (dias uteis, rotulo)
# 252 dias uteis = 1 ano (convencao ANBIMA). Ate 10A, faixa em que a ETTJ e ajustada.
TENOR_GRID = [
    (21, "1M"), (42, "2M"), (63, "3M"), (126, "6M"), (189, "9M"), (252, "1A"),
    (378, "1A6M"), (504, "2A"), (756, "3A"), (1008, "4A"), (1260, "5A"),
    (1512, "6A"), (1764, "7A"), (2016, "8A"), (2268, "9A"), (2520, "10A"),
]


def business_days_back(end: dt.date, n: int) -> list[dt.date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:  # seg-sex; feriados sao filtrados pela resposta vazia da ANBIMA
            out.append(d)
        d -= dt.timedelta(days=1)
    return out


def svensson(p: dict, t_years: float) -> float:
    """Taxa (% a.a.) da curva Svensson/NSS da ANBIMA no prazo t (em anos)."""
    x1 = p["l1"] * t_years
    x2 = p["l2"] * t_years
    f1 = (1.0 - math.exp(-x1)) / x1
    f2 = (1.0 - math.exp(-x2)) / x2
    r = (
        p["b1"]
        + p["b2"] * f1
        + p["b3"] * (f1 - math.exp(-x1))
        + p["b4"] * (f2 - math.exp(-x2))
    )
    return round(r * 100.0, 4)


def raw_to_grid(raw: dict) -> list[float]:
    p = raw["svensson_pref"]
    return [svensson(p, bd / 252.0) for bd, _ in TENOR_GRID]


def load_existing_dates() -> set[str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return {p.stem for p in RAW_DIR.glob("*.json")}


def collect() -> tuple[int, int]:
    have = load_existing_dates()
    wanted = business_days_back(dt.date.today(), LOOKBACK_BIZ_DAYS)
    missing = [d for d in wanted if d.isoformat() not in have]

    saved = skipped = misses = 0
    for d in missing:  # mais recente primeiro
        try:
            raw = fetch_ettj(d)
        except NoDataForDate:
            skipped += 1
            misses += 1
            print(f"  - {d}: sem ETTJ (fim de semana / feriado / nao publicado)")
        except Exception as err:  # noqa: BLE001 -- nao derruba o job
            skipped += 1
            misses += 1
            print(f"  ! {d}: erro: {err}")
        else:
            (RAW_DIR / f"{d.isoformat()}.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            saved += 1
            misses = 0
            print(f"  + {d}: arquivado (Svensson + {len(raw['vertices_pref'])} vertices publicados)")
        if misses >= MAX_CONSECUTIVE_MISSES:
            print(f"  (parando: {MAX_CONSECUTIVE_MISSES} dias seguidos sem dado)")
            break
    return saved, skipped


def rebuild_outputs() -> int:
    files = sorted(RAW_DIR.glob("*.json"))
    curves = []
    for p in files:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if "svensson_pref" not in raw:
            continue
        curves.append({"date": raw["date"], "rates": raw_to_grid(raw)})

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
                "source": "ANBIMA - Estrutura a Termo das Taxas de Juros (curva prefixada / ETTJ PREF)",
                "method": "curva Svensson (NSS) reconstruida dos parametros diarios da ANBIMA; 252 du = 1 ano",
                "tenors": [{"label": lab, "bd": bd} for bd, lab in TENOR_GRID],
                "curves": curves,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dates = [c["date"] for c in curves]
    INDEX_JSON.write_text(
        json.dumps(
            {
                "count": len(dates),
                "first": dates[0] if dates else None,
                "latest": dates[-1] if dates else None,
                "updated_at": now,
                "dates": dates,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return len(dates)


def main() -> int:
    print("== coletor curva-di (fonte: ANBIMA ETTJ) ==")
    saved, skipped = collect()
    total = rebuild_outputs()
    print(f"novos: {saved} | ignorados: {skipped} | total arquivado: {total}")
    if total == 0:
        print("AVISO: nenhuma curva arquivada -- verifique o parse em fetch_anbima.py")

    print("== importando B3 manual (b3-manual-inbox/) ==")
    b3_novos, b3_total = run_b3_manual()
    print(f"B3 manual: {b3_novos} novos | {b3_total} arquivados no total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
