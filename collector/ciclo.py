"""
Coletor do painel de ciclo: baixa as series do SGS/BCB, calcula z-score e
variacao em 12 meses, e grava docs/data/ciclo.json.

Decisoes que valem registro:

1. Series com tendencia (indice, saldo, cambio) tem z-score calculado sobre a
   VARIACAO EM 12 MESES, nao sobre o nivel. Z-score de nivel num indice que
   cresce sempre marca "extremo" e nao informa nada sobre o ciclo.

2. Toda serie carrega um limite de defasagem. Series do SGS sao descontinuadas
   em silencio -- a 21273 responde normalmente e esta parada desde 2014, a 7492
   desde jun/2025. Sem esse check, o painel exibiria numero morto como atual.

3. O termometro do bloco e a media dos z-scores ja orientados (sinal +1/-1), e
   ignora series marcadas como ambiguas (orient=0) ou defasadas.

Rodar: python collector/ciclo.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import statistics
import time

import requests

from series_ciclo import BLOCKS, SERIES

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "data" / "ciclo.json"

API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
HEADERS = {"User-Agent": "curva-di/ciclo (coletor publico)", "Accept": "application/json"}

LOOKBACK_YEARS = 10
HISTORY_POINTS = 72  # quantos pontos guardar para o sparkline


def fetch_series(code: int, *, retries: int = 3) -> list[tuple[dt.date, float]]:
    start = (dt.date.today() - dt.timedelta(days=365 * LOOKBACK_YEARS)).strftime("%d/%m/%Y")
    params = {"formato": "json", "dataInicial": start,
              "dataFinal": dt.date.today().strftime("%d/%m/%Y")}
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(API.format(code=code), params=params, headers=HEADERS, timeout=40)
            r.raise_for_status()
            out = []
            for row in r.json():
                try:
                    d = dt.datetime.strptime(row["data"], "%d/%m/%Y").date()
                    out.append((d, float(row["valor"])))
                except (ValueError, KeyError, TypeError):
                    continue
            out.sort(key=lambda x: x[0])
            return out
        except requests.RequestException as err:
            last_err = err
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"serie {code}: {last_err!r}")


def yoy(points: list[tuple[dt.date, float]]) -> list[tuple[dt.date, float]]:
    """Variacao percentual contra a observacao ~12 meses antes.

    Dois ponteiros: O(n). A versao ingenua (varrer o historico inteiro a cada
    ponto) levava minutos nas series diarias, que tem ~2.500 observacoes.
    """
    out: list[tuple[dt.date, float]] = []
    n = len(points)
    j = 0
    for d, v in points:
        alvo = d - dt.timedelta(days=365)
        while j + 1 < n and points[j + 1][0] <= alvo:
            j += 1
        cand = points[j]
        if j + 1 < n and abs((points[j + 1][0] - alvo).days) < abs((cand[0] - alvo).days):
            cand = points[j + 1]
        if cand[0] < d and abs((cand[0] - alvo).days) <= 45 and cand[1]:
            out.append((d, (v / cand[1] - 1) * 100.0))
    return out


def to_monthly(points: list[tuple[dt.date, float]]) -> list[tuple[dt.date, float]]:
    """Reamostra para mensal, pegando a ultima observacao de cada mes.

    Sem isso, series diarias entram no z-score com ~2.500 observacoes e series
    mensais com ~120. Alem de nao serem amostras comparaveis, a diaria e dominada
    por autocorrelacao: o desvio-padrao reflete quanto tempo a taxa ficou em cada
    nivel, nao quantas vezes ela mudou. O painel le ciclo em cadencia mensal, entao
    todas as series sao comparadas em cadencia mensal.
    """
    by_month: dict[tuple[int, int], tuple[dt.date, float]] = {}
    for d, v in points:
        key = (d.year, d.month)
        if key not in by_month or d > by_month[key][0]:
            by_month[key] = (d, v)
    return [by_month[k] for k in sorted(by_month)]


def zscore(values: list[float]) -> float | None:
    if len(values) < 12:
        return None
    mu = statistics.fmean(values)
    sd = statistics.pstdev(values)
    if sd == 0:
        return None
    return round((values[-1] - mu) / sd, 2)


def build_one(spec: dict) -> dict:
    pts = fetch_series(spec["code"])
    if not pts:
        raise RuntimeError(f"serie {spec['code']} voltou vazia")

    # "ultimo" e sempre a observacao mais recente de verdade (diaria, se for o caso);
    # o z-score, esse sim, e calculado em cadencia mensal para todas as series.
    last_date, last_value = pts[-1]
    lag_days = (dt.date.today() - last_date).days
    stale = lag_days > spec["max_lag"]

    monthly = to_monthly(pts)
    base = yoy(monthly) if spec["transform"] == "yoy" else monthly
    vals = [v for _, v in base]
    z = zscore(vals) if vals else None

    stats = None
    if len(vals) >= 12:
        stats = {
            "n": len(vals),
            "mean": round(statistics.fmean(vals), 4),
            "sd": round(statistics.pstdev(vals), 4),
            "start": base[0][0].isoformat(),
            "end": base[-1][0].isoformat(),
        }

    # variacao em 12 meses, sempre (para exibir), independente do transform
    y = yoy(monthly)
    chg12 = round(y[-1][1], 2) if y else None

    hist = base[-HISTORY_POINTS:]
    return {
        "code": spec["code"],
        "name": spec["name"],
        "block": spec["block"],
        "unit": spec["unit"],
        "freq": spec["freq"],
        "transform": spec["transform"],
        "orient": spec["orient"],
        "last": {"date": last_date.isoformat(), "value": round(last_value, 4)},
        "lag_days": lag_days,
        "stale": stale,
        "z": z,
        "stats": stats,   # n / media / desvio / janela -- para o z ser auditavel pelo arquivo
        "chg12m": chg12,
        "history": [[d.isoformat(), round(v, 4)] for d, v in hist],
    }


def block_scores(series: list[dict]) -> list[dict]:
    out = []
    for bid, label in BLOCKS:
        zs = [s["z"] * s["orient"] for s in series
              if s["block"] == bid and s["z"] is not None and s["orient"] != 0 and not s["stale"]]
        out.append({
            "id": bid,
            "label": label,
            "score": round(statistics.fmean(zs), 2) if zs else None,
            "n": len(zs),
        })
    return out


def main() -> int:
    print("== painel de ciclo (fonte: BCB SGS) ==")
    series, falhas = [], 0
    for spec in SERIES:
        try:
            s = build_one(spec)
        except Exception as err:  # noqa: BLE001 -- uma serie ruim nao derruba o painel
            falhas += 1
            print(f"  ! {spec['code']} {spec['name']}: {err}")
            continue
        series.append(s)
        flag = "DEFASADA" if s["stale"] else f"z={s['z']}"
        print(f"  + {s['code']:>6} {s['name'][:44]:<44} {s['last']['date']}  {flag}")

    blocks = block_scores(series)
    now = (dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
           .isoformat().replace("+00:00", "Z"))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "generated_at": now,
        "source": "Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS)",
        "method": ("z-score contra os últimos 10 anos; séries com tendência usam variação "
                   "em 12 meses como base. Termômetro do bloco = média dos z-scores orientados, "
                   "ignorando séries ambíguas ou defasadas."),
        "blocks": blocks,
        "series": series,
    }, ensure_ascii=False), encoding="utf-8")

    print("\n  termômetros:")
    for b in blocks:
        print(f"    {b['label']:<22} {b['score']}  (n={b['n']})")
    print(f"\n  séries: {len(series)} | falhas: {falhas} | "
          f"defasadas: {sum(1 for s in series if s['stale'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
