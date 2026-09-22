# Painel — Esteira de Pagamento

Painel das pendências abertas das ações **Solicitar pagamento** e **Verificar pagamento**
no Odoo MMP, separadas por etapa, grupo, tipo de pendência e idade.

## Link público

https://prdpaineis.github.io/painel-pagamento/ — atualizado sozinho todo dia às
07:00 (BRT) via GitHub Actions (`.github/workflows/atualizar-painel.yml`).
Sem autenticação: qualquer pessoa com o link vê os dados.

## Como atualizar manualmente

```bash
cd docs
python extrair.py
```

Ele gera, dentro de `docs/`:

| Arquivo | Para que serve |
|---|---|
| `index.html` | painel publicado no GitHub Pages, auto-contido. Também pode ser aberto com duplo clique localmente |
| `artefato.html` | mesmo painel sem o invólucro `<html>`, pra publicar como Artifact |
| `dados.json` | dados crus, pra jogar em Excel / Power BI |

`docs/` é a raiz servida pelo GitHub Pages. `index.html` é o único gerado que
vai pro git — de propósito, é o dado curado que o painel público mostra.
`dados.json` e `artefato.html` ficam só localmente (gitignored).

## Credenciais

Local: copie `docs/odoo-mmp.env.example` para `docs/odoo-mmp.env` e preencha
(ou aponte a variável `ODOO_ENV_FILE` para um .env que já exista).

No CI (GitHub Actions), as credenciais vêm dos Secrets do repositório
(`ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_PASSWORD`) — sem arquivo `.env`.

## De onde vêm os dados

| | |
|---|---|
| Fonte | Odoo MMP via XML-RPC |
| Modelo | `project.task.action.line` |
| Ações | `824` Solicitar pagamento · `825` Verificar pagamento |
| Escopo | somente `state = 'i'` (pendentes) |
| Classificação | `cumprimento_tipo_pendencia_id` — "Cumprimento Tipo da Pendência" |
| Grupo | `dossie_id` → `dossie.dossie.grupo_id` |
| Criado em | `create_date` da linha, que vira a faixa de idade |

## As duas etapas são diferentes

O campo **Cumprimento Tipo da Pendência só é preenchido no Verificar**. Por isso o painel
trata cada etapa com indicadores próprios:

- **Solicitar** — mede idade e dinheiro parado. Sem tabela de tipo de pendência.
- **Verificar** — o tipo é o eixo principal: `Solicitado` = aguardando o pagamento,
  `Análise` = pendente com o cliente, `Expirado` = prazo estourado.

## Ajustar as classificações

No topo do `docs/extrair.py`:

- `PENDENTE_CLIENTE = {"Análise"}`
- `RECUSA` = tipos `Recusada*`, `Erro em nossa solicitação`, `Erro de análise do cliente`,
  `Cancelada-Erro*`
- `RESP_NOSSA` / `RESP_CLIENTE` separam a responsabilidade da recusa

Edite os conjuntos e rode o extrator de novo.

## O que este repositório versiona (e o que não)

**Público e versionado, de propósito:** `docs/index.html`, gerado todo dia com
número de processo e valores de pagamento reais embutidos.

**Fora do repositório:** `docs/dados.json`, `docs/artefato.html` e qualquer
`.env`. Quem clonar roda o extrator local e gera os próprios.

## Arquivos versionados

- `docs/extrair.py` — extração e geração do painel
- `docs/painel_template.html` — o layout. O extrator injeta os dados no lugar de `/*__DADOS__*/`
- `docs/odoo-mmp.env.example` — modelo de credenciais
- `.github/workflows/atualizar-painel.yml` — automação diária
- `README.md`
