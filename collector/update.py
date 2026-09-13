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
from vertices import build_vertices

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "docs" / "data" / "raw"
CURVES_JSON = ROOT / "docs" / "data" / "curves.json"
REAL_JSON = ROOT / "docs" / "data" / "curves_real.json"
INDEX_JSON = ROOT / "docs" / "data" / "index.json"

LOOKBACK_BIZ_DAYS = 45
MAX_CONSECUTIVE_MISSES = 12

# vertices por data de vencimento (mm/aa), recalculados a cada run -- ver vertices.py
VERTICES = build_vertices()


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


def _grid(p: dict, curve_date: dt.date) -> list[float | None]:
    rates = []
    for _, vdate in VERTICES:
        t_years = (vdate - curve_date).days / 365.25
        rates.append(svensson(p, t_years) if t_years > 0 else None)
    return rates


def raw_to_grid(raw: dict) -> list[float | None]:
    """Curva nominal (prefixada)."""
    return _grid(raw["svensson_pref"], dt.date.fromisoformat(raw["date"]))


# A ANBIMA nao ajusta a curva IPCA abaixo de ~126 dias uteis (~0,5 ano): nao ha NTN-B
# curta o suficiente. Avaliar Svensson abaixo disso produz numero sem significado
# economico (testado: juro real de 14,6% e implicita negativa no vertice de 20 dias).
MIN_T_REAL_YEARS = 0.5


def raw_to_grid_real(raw: dict) -> list[float | None]:
    """Curva de juro real (IPCA+), dos parametros Svensson da curva IPCA da ANBIMA."""
    p = raw["svensson_ipca"]
    curve_date = dt.date.fromisoformat(raw["date"])
    rates = []
    for _, vdate in VERTICES:
        t_years = (vdate - curve_date).days / 365.25
        rates.append(svensson(p, t_years) if t_years >= MIN_T_REAL_YEARS else None)
    return rates


def implied_inflation(nom: list, real: list) -> list[float | None]:
    """Inflacao implicita (breakeven), geometrica: (1+nominal)/(1+real)-1.

    Mesma formula que a ANBIMA usa na coluna publicada -- conferida e batendo
    ate a 4a casa decimal.
    """
    out = []
    for n, r in zip(nom, real):
        if n is None or r is None:
            out.append(None)
        else:
            out.append(round(((1 + n / 100.0) / (1 + r / 100.0) - 1) * 100.0, 4))
    return out


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
    curves_real = []
    for p in files:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if "svensson_pref" not in raw:
            continue
        nom = raw_to_grid(raw)
        curves.append({"date": raw["date"], "rates": nom})
        if "svensson_ipca" in raw:
            real = raw_to_grid_real(raw)
            curves_real.append(
                {
                    "date": raw["date"],
                    "real": real,
                    "implicit": implied_inflation(nom, real),
                }
            )

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
                "method": "curva Svensson (NSS) reconstruida dos parametros diarios da ANBIMA, avaliada em cada data de vencimento",
                "tenors": [{"label": lab, "date": vdate.isoformat()} for lab, vdate in VERTICES],
                "curves": curves,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    REAL_JSON.write_text(
        json.dumps(
            {
                "generated_at": now,
                "source": "ANBIMA - ETTJ curva IPCA (juro real) + inflacao implicita",
                "method": "Svensson da curva IPCA avaliada em cada vencimento; implicita = (1+nominal)/(1+real)-1",
                "nota": "A ANBIMA ajusta a curva PREFIXADA ate ~2520 dias uteis (10 anos). Alem disso, "
                        "tanto a nominal quanto a implicita sao extrapolacao do modelo, nao mercado observado.",
                "tenors": [{"label": lab, "date": vdate.isoformat()} for lab, vdate in VERTICES],
                "curves": curves_real,
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
