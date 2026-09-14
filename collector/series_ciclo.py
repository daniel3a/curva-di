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
    ("atividade", "Atividade"),
    ("juros", "Juros e inflação"),
    ("credito", "Crédito e estresse"),
    ("imobiliario", "Imobiliário"),
    ("cambio", "Câmbio"),
]

SERIES = [
    # --- atividade ---------------------------------------------------------
    # Bloco deliberadamente magro por enquanto: so o IBC-Br tem API publica no BCB.
    # Emprego (CAGED), PIB (IBGE/SIDRA) e confianca (FGV) entram quando abrirmos
    # outras fontes. Ate la, este termometro le atividade por uma serie so -- o que
    # esta declarado na pagina, para ninguem confundir com leitura robusta.
    dict(code=24363, name="IBC-Br (dessazonalizado)", block="atividade",
         unit="índice", freq="mensal", transform="yoy", orient=+1, max_lag=125),

    # --- juros e inflacao --------------------------------------------------
    # A Selic efetiva (1178) foi removida: depois que o z-score passou a ser
    # calculado em cadencia mensal, a unica vantagem dela sobre a meta (leitura
    # diaria) deixou de existir, e manter as duas dobrava o peso de "juros" no bloco.
    dict(code=432, name="Meta Selic (Copom)", block="juros",
         unit="% a.a.", freq="reuniao", transform="level", orient=-1, max_lag=120),
    dict(code=13522, name="IPCA acumulado em 12 meses", block="juros",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=75),
    dict(code=433, name="IPCA no mês", block="juros",
         unit="%", freq="mensal", transform="level", orient=-1, max_lag=75),
    dict(code=189, name="IGP-M no mês", block="juros",
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
