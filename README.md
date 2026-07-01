# Grupo SBF · Agente de Triagem de Currículos

Triagem de candidatos para **operações de varejo** com IA **auditável, anti-viés e mensurável**.
Recebe um lote de currículos contra uma vaga e devolve, para cada candidato: **aderência ao perfil
(com justificativa), pontos de destaque, lacunas e recomendação — avançar / avaliar / não avançar**.

> **Tese (neurossimbólica):** a IA **só extrai sinais** do CV → o **Python aplica uma rubrica ponderada
> e determinística** → o app **persiste e mede**. A nota e o ranking **nunca** saem da IA; saem de um
> cálculo que o RH lê, contesta e ajusta. O diferencial é a **camada de métricas** (taxa de
> auto-decisão, custo e latência por CV) — resposta direta ao gargalo nº 3 do case
> ("600+ agentes sem impacto mensurável").

## O que faz

1. **Vaga** — você cola a descrição; a IA propõe uma **rubrica ponderada** (7 critérios, knockouts);
   você edita e **congela** antes de ver qualquer CV (a "régua de ouro").
2. **Upload** — sobe N currículos (PDF/TXT/DOCX); o **cegamento de PII** roda no upload (LGPD) e o
   lote entra numa fila assíncrona (pode sair da tela).
3. **Resultado** — ranking nas **3 zonas** (Avançar / Avaliar / Não avançar) com a **taxa de
   auto-decisão** em destaque; cada ficha traz nota, justificativa, destaques e lacunas rastreáveis.
4. **Métricas** — painel operacional: auto-decisão vs. alvo, **custo e latência por CV**, cache e
   distribuição de zonas.
5. **Configurações (low-code)** — **cola a chave de API e roda**; ajusta modelos por estágio,
   thresholds e o fallback de provedor pela própria tela, sem mexer no código.

## Como rodar (passo a passo)

**Backend, frontend e banco sobem juntos:** o FastAPI serve o `frontend/dist` (já commitado) e o
**SQLite é criado sozinho** no primeiro start — sem migração nem comando de banco. Escolha um caminho:

**Opção A — Docker (recomendado; só precisa do Docker):**

```bash
docker compose up --build       # → http://localhost:8000
```

**Opção B — Python (sem Node; precisa de Python 3.12+):**

```bash
pip install -r backend/requirements.txt
make run                         # → http://localhost:8000
```

Depois de subir, abra **http://localhost:8000 → Configurações**, cole a **chave da Claude** e clique
**Testar**. O app sobe sem chave; a triagem é que exige a chave. *(Opcional: `cp .env.example .env` e
preencher `ANTHROPIC_API_KEY` em vez de colar na UI.)*

- **Dev (hot reload, precisa de Node):** `make install && make dev` — API `:8000` + Vite `:5173`
- **Testes:** `make test` (núcleo determinístico — score, portões, calibração, zonas, cegamento)

## Como testar em 2 minutos

1. `make run` → abra http://localhost:8000 → **Configurações** → cole a chave da Claude → **Testar**.
2. **Vagas** → crie uma vaga (ex.: "Vendedor de loja"); a IA propõe a rubrica → **congele**.
3. **Suba os currículos de exemplo** de
   [`backend/data/benchmark/curriculos/`](backend/data/benchmark/curriculos/) — 8 CVs sintéticos
   `.txt` (sem PII); a UI aceita `.txt`.
4. Veja o **ranking**, abra uma **ficha** (os 4 outputs) e a tela **Métricas**.

## Stack & decisões

| Escolha | Por quê |
|---|---|
| **FastAPI + Pydantic** | tipado; o schema vira contrato da API e do pipeline |
| **Claude (`messages.parse`)** | saída **estruturada validada**; modelos mistos por estágio (Haiku nos simples, Sonnet na decisão) |
| **SQLite + SQLAlchemy** | zero setup; ORM abstrai migração futura para Postgres |
| **Fila asyncio in-process** | sem Celery/Redis — fiel ao "só a chave de API"; retomável após restart |
| **React + Vite + TS** | SPA leve servida pelo próprio FastAPI (um processo só) |

**A nota é 100% Python** (testada e auditável); a IA não decide nota nem ranking. Em lentidão ou queda
de provedor, um **roteador multi-provedor** rerouteia Claude → OpenAI/Gemini — a fila não trava.

## Limitações (honestas)

- **Pesos e limiares** são pontos de partida calibráveis, não validados empiricamente.
- **Métricas de qualidade (consistência, Cohen's κ, paridade)** são **roadmap**: o benchmark sintético
  com pares de viés já é a base metodológica, mas o cálculo ainda não é rodável nesta entrega.
- **PDFs escaneados** precisariam de OCR (Claude Vision) — fora do MVP; cobrimos texto selecionável.
- **Segurança (demo):** a PII é redigida **antes** de ir à IA e o CV original fica só local (para o RH
  abrir na ficha). Sem login/rate-limit por ser um demo local de um único avaliador — produção
  acrescentaria autenticação e um cofre de segredos.

## Ferramentas de IA usadas

Desenvolvido com **Claude (Claude Code)** — scaffolding, pipeline neurossimbólico, design system e
testes. A própria solução chama a **Claude API** (`messages.parse` + prompt caching) nos estágios de
julgamento.


