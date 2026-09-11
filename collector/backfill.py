"""
Preenche um intervalo explicito de datas (uso pontual).

Normalmente NAO e necessario: update.py ja tenta os ultimos 45 dias uteis a cada
run, e na primeira execucao isso baixa tudo o que a B3 tem on-line.
Use este script so para forcar um intervalo especifico.

    python collector/backfill.py 2026-08-13 2026-09-10

Depois rode `python collector/update.py` (ou deixe o job diario) para reconstruir
docs/data/curves.json.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import time

from fetch_b3 import NoDataForDate, fetch_pre_curve

RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "raw"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python collector/backfill.py AAAA-MM-DD AAAA-MM-DD")
        return 2
    start, end = (dt.date.fromisoformat(x) for x in argv)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    d = start
    saved = skipped = 0
    while d <= end:
        if d.weekday() < 5:
            dest = RAW_DIR / f"{d.isoformat()}.json"
            if dest.exists():
                print(f"  = {d}: ja arquivado")
            else:
                try:
                    raw = fetch_pre_curve(d)
                except NoDataForDate:
                    skipped += 1
                    print(f"  - {d}: sem dado")
                except Exception as err:  # noqa: BLE001
                    skipped += 1
                    print(f"  ! {d}: {err}")
                else:
                    dest.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
                    saved += 1
                    print(f"  + {d}: {len(raw['rows'])} vertices")
                time.sleep(1.5)
        d += dt.timedelta(days=1)

    print(f"\nnovos: {saved} | sem dado: {skipped}")
    print("agora rode: python collector/update.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
