# Inbox manual — curva DI1 da B3

Solte aqui o arquivo que você baixar da página da B3
([Taxas referenciais BM&FBOVESPA](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-derivativos/precos-referenciais/taxas-referenciais-bm-fbovespa/)).

Ainda não escrevi o parser — falta uma amostra real do arquivo (formato e colunas)
para saber como ler. Assim que tiver isso, um passo do coletor passa a:

1. ler qualquer arquivo novo aqui,
2. extrair a curva DI1 da data,
3. arquivar em `docs/data/raw_b3/AAAA-MM-DD.json`,
4. reconstruir `docs/data/curves_b3.json`,
5. e o dashboard ganha o seletor **ANBIMA ETTJ × B3 DI1** + a view de spread
   (arbitragem) por vértice.

Até lá, pode ir soltando os arquivos aqui mesmo (nada é perdido) — só não são
processados ainda.
