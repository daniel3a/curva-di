# curva-di

Arquivo diário da **curva de juros prefixada brasileira** + dashboard interativo.

A fonte pública mantém só poucas semanas de histórico on-line. Este repositório
baixa a curva todo dia útil (GitHub Actions), guarda cada pregão e publica um
dashboard (GitHub Pages) para comparar datas, defasagens (d-1 … d-360) e pregões
de reunião do Copom.

- **Fonte:** [ANBIMA — Estrutura a Termo das Taxas de Juros (ETTJ)](https://www.anbima.com.br/informacoes/est-termo/),
  curva prefixada de títulos públicos. É a curva de juros de referência do mercado
  local e anda praticamente colada na curva DI (diferença = spread DI×pré, poucos bps).
- **Por que não a B3 direto:** o portal legado da B3 (`www2.bmf.com.br`) — taxas
  referenciais e ajustes do DI1 — está fora do ar / sendo desativado. A ETTJ da
  ANBIMA é a alternativa gratuita e estável. Puxar o DI1 exato fica para a fase 2,
  se/quando a B3 publicar um endpoint novo.
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
  fetch_anbima.py   baixa a ETTJ de uma data (parâmetros Svensson + tabelas publicadas)
  update.py         roda no Actions: baixa os pregões que faltam dos últimos 45 dias
                    úteis, arquiva em docs/data/raw/, reconstrói curves.json + index.json
  backfill.py       uso pontual: força um intervalo de datas
.github/workflows/daily.yml   agenda (cron) + commit automático
docs/
  index.html            dashboard (ECharts); lê data/curves.json
  data/raw/AAAA-MM-DD.json   arquivo de cada pregão: parâmetros Svensson (PREF e IPCA) +
                            vértices ETTJ PREF publicados + trecho curto (CIRCULAR 3.361)
  data/curves.json          curva avaliada numa grade fixa (1M…10A) pela fórmula de Svensson
  data/index.json           lista de datas disponíveis
```

A curva é reconstruída pela fórmula **Svensson (NSS)** a partir dos parâmetros
diários da ANBIMA (`252 dias úteis = 1 ano`) — bate com os vértices publicados
pela ANBIMA com diferença < 0,1 ponto-base. Guardamos também as tabelas
publicadas em cada `raw/*.json` para conferência.

O dashboard funciona **antes** de existir dado real: mostra uma curva de exemplo
com aviso, e troca pela curva da ANBIMA assim que `curves.json` existir.

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
- [ ] **Segunda série: DI1 (ajustes do pregão da B3)** — casa exatamente com o
      gráfico do Valor (vértices = contratos). Depende de a B3 publicar um endpoint
      novo funcional.
- [ ] **Curva IPCA / inflação implícita** — já vem no mesmo arquivo da ANBIMA,
      só falta expor no dashboard.
