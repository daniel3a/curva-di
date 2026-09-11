"""
Grade de vertices do dashboard (compartilhada entre ANBIMA e B3), no mesmo estilo
do grafico "Curva de juros" do Valor: rotulo por MES/ANO de vencimento, nao por
prazo relativo.

Regra (a partir de hoje, ano atual = A):
  i.   mensal, do mes seguinte ate dezembro de A+2
  ii.  meses de reuniao do Copom (jan, mar, mai, jun, jul, set, nov, dez),
       nos anos A+3 a A+5
  iii. anual em janeiro, dos anos A+6 a A+15

Recalculada a cada run (com base na data de hoje) e aplicada a TODAS as curvas
arquivadas, para que todo mundo compartilhe o mesmo eixo -- igual ao gráfico do
Valor, que planta o eixo em datas fixas e avalia cada curva (de cada pregao)
nesses mesmos pontos.
"""
from __future__ import annotations

import datetime as dt

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
COPOM_MONTHS = [1, 3, 5, 6, 7, 9, 11, 12]


def _label(y: int, m: int) -> str:
    return f"{MESES[m - 1]}/{str(y)[2:]}"


def _add_month(y: int, m: int) -> tuple[int, int]:
    m += 1
    if m > 12:
        y, m = y + 1, 1
    return y, m


def build_vertices(today: dt.date | None = None) -> list[tuple[str, dt.date]]:
    """Devolve [(rotulo, data_do_vertice), ...] em ordem cronologica."""
    today = today or dt.date.today()
    y0, m0 = today.year, today.month
    verts: list[tuple[str, dt.date]] = []

    # i. mensal: mes seguinte -> dezembro de y0+2
    y, m = _add_month(y0, m0)
    end = (y0 + 2, 12)
    while (y, m) <= end:
        verts.append((_label(y, m), dt.date(y, m, 1)))
        y, m = _add_month(y, m)

    # ii. meses de copom, anos y0+3 .. y0+5
    for yy in range(y0 + 3, y0 + 6):
        for mm in COPOM_MONTHS:
            verts.append((_label(yy, mm), dt.date(yy, mm, 1)))

    # iii. anual em janeiro, anos y0+6 .. y0+15
    for yy in range(y0 + 6, y0 + 16):
        verts.append((_label(yy, 1), dt.date(yy, 1, 1)))

    return verts


if __name__ == "__main__":
    vs = build_vertices()
    print(f"{len(vs)} vertices, de {vs[0][0]} a {vs[-1][0]}")
    for lab, d in vs:
        print(f"  {lab}  ({d.isoformat()})")
