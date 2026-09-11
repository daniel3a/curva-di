# curva-di

Arquivo diário da **curva de juros prefixada brasileira** + dashboard interativo.

A fonte pública mantém só poucas semanas de histórico on-line. Este repositório
baixa a curva todo dia útil (GitHub Actions), guarda cada pregão e publica um
dashboard (GitHub Pages) para comparar datas, defasagens (d-1 … d-360) e pregões
de reunião do Copom.

- **Fonte automática:** [ANBIMA — Estrutura a Termo das Taxas de Juros (ETTJ)](https://www.anbima.com.br/informacoes/est-termo/),
  curva prefixada de títulos públicos. É a curva de juros de referência do mercado
  local e anda praticamente colada na curva DI (diferença = spread DI×pré, poucos bps).
- **Fonte manual: B3 (DI×Pré de verdade)** — a B3 publica a curva exata em
  "Mercado de Derivativos ▸ Taxas de Mercado para Swaps"
  ([Pesquisa por Pregão](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/)),
  mas o download passa por proteção anti-bot (Cloudflare) que não dá pra automatizar
  sem navegador. Por isso é manual: baixe o arquivo pelo navegador e solte em
  `b3-manual-inbox/`. O coletor importa sozinho a partir daí.
- **Por que a ANBIMA e não a B3 no dia a dia:** o portal legado da B3
  (`www2.bmf.com.br`) está fora do ar; o novo (`drp.b3.com.br`) tem proteção
  anti-bot. A ANBIMA é a alternativa automática, gratuita e estável — e o
  dashboard mostra a diferença entre as duas (seção "Arbitragem") sempre que
  houver um arquivo B3 importado pra aquela data.
- **Custo:** zero. Actions e Pages são gratuitos em repositório público.

---

## Configuração (uma vez, tudo pelo navegador)

1. **Subir os arquivos** — na página do repositório → **Add file ▸ Upload files**
   → arraste **todo o conteúdo** desta pasta → **Commit changes**.
   Se a pasta `.github` não subir pelo arrastar, crie o arquivo manualmente:
   **Add file ▸ Create new file**, nome `.github/workflows/daily.yml`, cole o conteúdo.

2. **Ligar o Actions** — aba **Actions** → **"I understand my workflows, enable them"**.
   Em **Settings ▸ Actions ▸ General ▸ Workflow permissions**, marque
   **"Read and write permissions"** (deixa o job salvar os dados).

3. **Rodar agora** — aba **Actions** → **"Coletar curva B3"** → **Run workflow**.
   Baixa ~2 meses de pregões que a ANBIMA tem on-line e commita em `docs/data/`.
   *(O bundle já vem com esses dados; este passo só pega o que faltar.)*

4. **Ligar o Pages** — **Settings ▸ Pages** → *Source*: **Deploy from a branch**
   → branch **`main`**, pasta **`/docs`** → **Save**.
   Endereço: `https://daniel3a.github.io/curva-di/`

Depois disso o job roda sozinho ~20:15 (BRT) nos dias úteis, com uma segunda
passada de segurança na manhã seguinte.

---

## Como funciona

```
collector/
  fetch_anbima.py     baixa a ETTJ de uma data (parâmetros Svensson + tabelas publicadas)
  import_b3_manual.py varre b3-manual-inbox/ e importa os arquivos da B3
  update.py           roda no Actions: ANBIMA (últimos 45 dias úteis) + importa a inbox B3;
                      reconstrói curves.json, curves_b3.json e index.json
  backfill.py         uso pontual: força um intervalo de datas (só ANBIMA)
.github/workflows/daily.yml   agenda (cron) + commit automático
b3-manual-inbox/       solte aqui os arquivos "Taxas de Mercado para Swaps" baixados da B3
docs/
  index.html                    dashboard (ECharts); lê curves.json + curves_b3.json
  data/raw/AAAA-MM-DD.json      pregão ANBIMA: parâmetros Svensson + tabelas publicadas
  data/raw_b3/AAAA-MM-DD.json   pregão B3: vértices brutos do arquivo importado
  data/curves.json              curva ANBIMA numa grade fixa (1M…10A), via fórmula de Svensson
  data/curves_b3.json           curva B3 na mesma grade, via interpolação linear
  data/index.json               lista de datas disponíveis (ANBIMA)
```

A curva ANBIMA é reconstruída pela fórmula **Svensson (NSS)** a partir dos
parâmetros diários — bate com os vértices publicados pela ANBIMA com diferença
< 0,1 ponto-base. A curva B3 é interpolada linearmente sobre o arquivo bruto
(que já vem bem granular, ~280 vértices). As duas usam a mesma grade de
vértices (em dias úteis), então o spread por vértice é uma subtração direta —
sem viés de método.

O dashboard funciona **antes** de existir dado real: mostra uma curva de exemplo
com aviso, e troca pela curva da ANBIMA assim que `curves.json` existir. A seção
de arbitragem só aparece quando existir ao menos um pregão com dado da B3.

---

## Importar um pregão da B3 (manual)

1. Na [Pesquisa por Pregão](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/),
   baixa o arquivo **"Mercado de Derivativos - Taxas de Mercado para Swaps"** do dia.
2. Solta o arquivo (sem renomear) em `b3-manual-inbox/` — o coletor acha a data pelo
   nome do arquivo (procura `AAAAMMDD`).
3. Sobe pro GitHub (commit + push). No próximo `python collector/update.py`
   (local ou no job diário) ele é importado sozinho e o dashboard ganha a
   comparação daquela data em "Arbitragem ANBIMA × B3".

---

## Rodar localmente (opcional — Python 3.11+)

```bash
pip install -r requirements.txt
python collector/update.py                            # baixa o que falta + reconstrói curves.json
python collector/backfill.py 2026-07-01 2026-09-10    # (opcional) força um intervalo
python -m http.server -d docs 8000                    # abre http://localhost:8000
```

---

## Roadmap

- [ ] **Notícias do dia** — coletor lê RSS (Valor, InfoMoney, Reuters, Broadcast)
      e grava manchetes + links em `docs/data/news.json`. Custo zero.
- [ ] **Comentário automático (IA, opcional)** — Claude Sonnet 5 redige 2–3 frases
      a partir da variação da curva + manchetes, citando os links. ~R$1/mês;
      exige `ANTHROPIC_API_KEY` em **Settings ▸ Secrets and variables ▸ Actions**.
      Desligado por padrão.
- [x] **Segunda série: B3 DI×Pré** — importação manual (`b3-manual-inbox/`) +
      seção de arbitragem no dashboard. Automatizar fica pendente de a B3 abrir
      um endpoint sem proteção anti-bot.
- [ ] **Curva IPCA / inflação implícita** — já vem no mesmo arquivo da ANBIMA,
      só falta expor no dashboard.
