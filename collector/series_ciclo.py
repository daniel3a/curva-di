"""
Catalogo curado de series do SGS/BCB para o painel de ciclo (Fase 1).

Cada serie foi verificada por chamada direta a API: o codigo resolve, a ultima
observacao e recente e a magnitude e plausivel. Series cujo NOME eu nao consegui
confirmar com seguranca ficaram de fora -- e melhor um painel menor e correto do
que um maior com rotulo errado.

Campos:
  code      codigo no SGS
  name      nome da serie
  block     bloco do painel (ver BLOCKS)
  unit      unidade, para exibicao
  freq      "diaria" | "mensal" | "reuniao"
  transform "level"  -> z-score sobre o proprio nivel (taxas, que revertem a media)
            "yoy"    -> z-score sobre a variacao em 12 meses (indices e saldos, que
                        tem tendencia; z-score de nivel num indice em tendencia da
                        sempre "extremo" e nao significa nada)
  orient    +1 se subir e melhor para o ciclo, -1 se subir e pior, 0 se ambiguo
            (ambiguo entra no painel mas fica fora do termometro do bloco)
  max_lag   dias de atraso tolerados antes de marcar a serie como defasada
"""
from __future__ import annotations

BLOCKS = [
    ("atividade", "Atividade e juros"),
    ("credito", "Crédito e estresse"),
    ("imobiliario", "Imobiliário"),
    ("cambio", "Câmbio"),
]

SERIES = [
    # --- atividade e juros -------------------------------------------------
    # IBC-Br sai com ~50 dias de defasagem; as vesperas da proxima divulgacao a
    # observacao mais recente chega a ~110 dias de idade sem que haja problema algum.
    dict(code=24363, name="IBC-Br (dessazonalizado)", block="atividade",
         unit="índice", freq="mensal", transform="yoy", orient=+1, max_lag=125),
    dict(code=432, name="Meta Selic (Copom)", block="atividade",
         unit="% a.a.", freq="reuniao", transform="level", orient=-1, max_lag=120),
    dict(code=1178, name="Selic efetiva anualizada", block="atividade",
         unit="% a.a.", freq="diaria", transform="level", orient=-1, max_lag=12),
    dict(code=13522, name="IPCA acumulado em 12 meses", block="atividade",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=75),
    dict(code=433, name="IPCA no mês", block="atividade",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=75),
    dict(code=189, name="IGP-M no mês", block="atividade",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=75),

    # --- credito e estresse ------------------------------------------------
    dict(code=21082, name="Inadimplência da carteira — total", block="credito",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=95),
    dict(code=21086, name="Inadimplência PJ — recursos livres", block="credito",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=95),
    dict(code=29037, name="Endividamento das famílias", block="credito",
         unit="% da renda 12m", freq="mensal", transform="level", orient=-1, max_lag=110),
    dict(code=29038, name="Endividamento das famílias (ex-habitacional)", block="credito",
         unit="% da renda 12m", freq="mensal", transform="level", orient=-1, max_lag=110),
    dict(code=20539, name="Saldo da carteira de crédito — total", block="credito",
         unit="R$ milhões", freq="mensal", transform="yoy", orient=+1, max_lag=95),
    dict(code=20631, name="Concessões de crédito — total", block="credito",
         unit="R$ milhões", freq="mensal", transform="yoy", orient=+1, max_lag=95),

    # --- imobiliario -------------------------------------------------------
    dict(code=21340, name="IVG-R — valor de garantia de imóvel residencial", block="imobiliario",
         unit="índice", freq="mensal", transform="yoy", orient=+1, max_lag=110),

    # --- cambio ------------------------------------------------------------
    dict(code=1, name="Dólar PTAX (venda)", block="cambio",
         unit="R$/US$", freq="diaria", transform="yoy", orient=0, max_lag=12),
]
