# curva-di

Arquivo diário da **curva de juros PRÉ (DI × Pré) da B3** + dashboard interativo.

A B3 mantém só ~1 mês de histórico on-line na consulta pública. Este repositório
baixa a curva todo dia útil (GitHub Actions), guarda cada pregão e publica um
dashboard (GitHub Pages) para comparar datas, defasagens (d-1 … d-360) e pregões
de reunião do Copom.

- **Fonte:** [B3 — Taxas Referenciais BM&FBOVESPA](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-derivativos/precos-referenciais/taxas-referenciais-bm-fbovespa/) (`slcTaxa=PRE`), a mesma página usada pelo pacote R `rb3`.
- **Custo:** zero. Actions e Pages são gratuitos em repositório público.

---

## Configuração (uma vez, tudo pelo navegador)

O repositório já existe. Falta subir os arquivos e ligar duas coisas.

1. **Subir os arquivos**
   Na página do repositório → **Add file ▸ Upload files** → arraste **todo o
   conteúdo** desta pasta (`collector/`, `docs/`, `.github/`, `requirements.txt`,
   `README.md`, `.gitignore`) → **Commit changes**.
   *(O arrastar-e-soltar do GitHub preserva as subpastas.)*

2. **Ligar o Actions**
   Aba **Actions** → botão **“I understand my workflows, enable them”**.

3. **Popular o histórico agora** (sem esperar o horário do cron)
   Aba **Actions** → workflow **“Coletar curva B3”** → **Run workflow** ▸ **Run
   workflow**. Em ~1–2 min ele baixa tudo que a B3 tem on-line (~20 pregões) e
   faz o commit em `docs/data/`.

4. **Ligar o Pages**
   **Settings ▸ Pages** → *Source*: **Deploy from a branch** → branch **`main`**,
   pasta **`/docs`** → **Save**. Em ~1 min aparece o endereço:
   `https://daniel3a.github.io/curva-di/`

Pronto. A partir daí o job roda sozinho ~20:15 (BRT) nos dias úteis, com uma
segunda passada de segurança na manhã seguinte.

---

## Como funciona

```
collector/
  fetch_b3.py   baixa e faz o parse da tabela PRÉ de uma data (dump fiel)
  update.py     roda no Actions: baixa os pregões que faltam dos últimos 45 dias
                úteis, arquiva em docs/data/raw/, reconstrói curves.json + index.json
  backfill.py   uso pontual: força um intervalo de datas
.github/workflows/daily.yml   agenda (cron) + commit automático
docs/
  index.html            dashboard (ECharts); lê data/curves.json
  data/raw/AAAA-MM-DD.json   arquivo bruto de cada pregão (nunca sobrescrito)
  data/curves.json          curvas interpoladas numa grade fixa de vértices (o dashboard usa este)
  data/index.json           lista de datas disponíveis
```

O dashboard funciona **antes** de existir dado real: mostra uma curva de exemplo
com um aviso, e passa a mostrar a curva da B3 assim que `curves.json` for gerado.

### Conferir o parse no primeiro run

`fetch_b3.py` assume que a tabela PRÉ tem as colunas, em ordem:
`prazo (dias corridos) | taxa base 252 | taxa base 360`.
Depois do primeiro run, abra um arquivo em `docs/data/raw/` e confira se
`rows` bate com isso (primeira coluna = prazo crescente, segunda = taxa ~13–15).
Se a ordem for outra, é um ajuste de 1 linha em `raw_to_grid()` (em `update.py`)
e em `columns` (em `fetch_b3.py`).

---

## Rodar localmente (opcional — precisa de Python 3.11+)

```bash
pip install -r requirements.txt
python collector/backfill.py 2026-08-13 2026-09-10   # baixa um intervalo
python collector/update.py                            # reconstrói curves.json
# abrir docs/index.html num servidor local, ex.:
python -m http.server -d docs 8000   # http://localhost:8000
```

---

## Roadmap

- [ ] **Notícias do dia** — coletor lê RSS (Valor, InfoMoney, Reuters, Broadcast)
      e grava manchetes + links em `docs/data/news.json`. Custo zero.
- [ ] **Comentário automático (IA, opcional)** — Claude Sonnet 5 redige 2–3 frases
      a partir da variação da curva + manchetes, citando os links. ~R$1/mês;
      exige `ANTHROPIC_API_KEY` em **Settings ▸ Secrets and variables ▸ Actions**.
      Desligado por padrão.
- [ ] **Segunda série: DI1 (ajustes do pregão)** — casa exatamente com o gráfico
      do Valor (vértices = contratos). Endpoint mais instável, fica para a fase 2.
