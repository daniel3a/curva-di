"""
Roda todo dia (GitHub Actions). Faz:

  1. olha quais pregoes ja estao arquivados em docs/data/raw/
  2. tenta baixar os pregoes ausentes dos ultimos N dias uteis (a B3 so mantem ~1 mes)
  3. grava o dump fiel de cada pregao novo em docs/data/raw/AAAA-MM-DD.json
  4. reconstroi docs/data/curves.json (curvas interpoladas numa grade fixa de vertices)
     e docs/data/index.json (lista de datas disponiveis)

Nunca falha o job por causa de um dia sem dado ou de instabilidade da B3 -- o proximo
run preenche o buraco. Rodar localmente: python collector/update.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

from fetch_b3 import NoDataForDate, fetch_pre_curve

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "docs" / "data" / "raw"
CURVES_JSON = ROOT / "docs" / "data" / "curves.json"
INDEX_JSON = ROOT / "docs" / "data" / "index.json"

# quantos dias uteis para tras tentar preencher a cada run
LOOKBACK_BIZ_DAYS = 45
# para de tentar depois de tantos dias seguidos sem dado / com erro (evita marteladas)
MAX_CONSECUTIVE_MISSES = 12

# grade fixa de vertices para o dashboard: (dias corridos, rotulo)
TENOR_GRID = [
    (30, "1M"), (60, "2M"), (91, "3M"), (182, "6M"), (273, "9M"),
    (365, "1A"), (548, "1A6M"), (730, "2A"), (1095, "3A"), (1460, "4A"),
    (1825, "5A"), (2555, "7A"), (2920, "8A"), (3650, "10A"), (4380, "12A"),
]


def business_days_back(end: dt.date, n: int) -> list[dt.date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:  # seg-sex; feriados sao filtrados pela resposta da B3
            out.append(d)
        d -= dt.timedelta(days=1)
    return out


def linear_interp(xs: list[float], ys: list[float], x: float) -> float | None:
    """Interpolacao linear simples em xs (crescente). Nao extrapola no longo."""
    if not xs:
        return None
    if x <= xs[0]:
        return ys[0] if x >= xs[0] * 0.5 else None
    if x >= xs[-1]:
        return None
    for i in range(1, len(xs)):
        if xs[i] >= x:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return round(ys[i - 1] + t * (ys[i] - ys[i - 1]), 4)
    return None


def raw_to_grid(raw: dict) -> list[float | None]:
    """Pega o dump fiel e devolve a taxa em cada vertice da TENOR_GRID."""
    rows = [r for r in raw["rows"] if r[0] is not None and r[1] is not None]
    xs = [float(r[0]) for r in rows]
    ys = [float(r[1]) for r in rows]  # rate_252 (% a.a.)
    return [linear_interp(xs, ys, float(days)) for days, _ in TENOR_GRID]


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
            raw = fetch_pre_curve(d)
        except NoDataForDate:
            skipped += 1
            misses += 1
            print(f"  - {d}: sem pregao / sem dado")
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
            n = len(raw["rows"])
            print(f"  + {d}: {n} vertices arquivados")
        if misses >= MAX_CONSECUTIVE_MISSES:
            print(f"  (parando: {MAX_CONSECUTIVE_MISSES} dias seguidos sem dado)")
            break
    return saved, skipped


def rebuild_outputs() -> int:
    files = sorted(RAW_DIR.glob("*.json"))
    curves = []
    for p in files:
        raw = json.loads(p.read_text(encoding="utf-8"))
        curves.append({"date": raw["date"], "rates": raw_to_grid(raw)})

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": "B3 - Taxas Referenciais BM&FBOVESPA (curva PRE / DI x Pre)",
        "interpolation": "linear em dias corridos sobre a taxa base 252 (% a.a.)",
        "tenors": [{"label": lab, "days": d} for d, lab in TENOR_GRID],
        "curves": curves,
    }
    CURVES_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    dates = [c["date"] for c in curves]
    INDEX_JSON.write_text(
        json.dumps(
            {
                "count": len(dates),
                "first": dates[0] if dates else None,
                "latest": dates[-1] if dates else None,
                "updated_at": payload["generated_at"],
                "dates": dates,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return len(dates)


def main() -> int:
    print("== coletor curva-di ==")
    saved, skipped = collect()
    total = rebuild_outputs()
    print(f"novos: {saved} | ignorados: {skipped} | total arquivado: {total}")
    if total == 0:
        print("AVISO: nenhuma curva arquivada ainda -- verifique o parse em fetch_b3.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
