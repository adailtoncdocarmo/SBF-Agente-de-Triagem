# CLAUDE.md — Agente de Triagem de Currículos (Case Grupo SBF)

> **Projeto:** Product Builder, IA & Automação · Gente — Opção A (triagem de candidatos para varejo).
> **Estado:** Fase 1 (esqueleto que sobe e roda vazio). Funcionalidades em [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md).
>
> ⚠️ Este `CLAUDE.md` governa **este** repositório. Ignore qualquer `CLAUDE.md`
> herdado de pastas-pai (ex.: o do projeto "QuantIA", que usa outra stack e
> proíbe FastAPI/React) — **não se aplica aqui**.

---

## 1. O que é

Recebe o currículo de um candidato e devolve uma **triagem estruturada**:
aderência ao perfil da vaga (com justificativa), pontos de destaque, lacunas e
recomendação (`avançar` / `avaliar` / `não avançar`).

**Tese central (neurossimbólica):**
> A **IA só extrai sinais** do currículo → o **Python aplica uma rubrica ponderada
> e determinística** da vaga → o app **persiste e mede**.
> A nota **nunca** sai da IA; sai de um cálculo auditável que o RH consegue ler e ajustar.

O diferencial competitivo é a **camada de métricas** (consistência, paridade,
latência, custo) — resposta direta ao gargalo nº 3 do case ("600+ agentes sem
impacto mensurável").

## 2. Stack

```
Backend : FastAPI + Uvicorn · Pydantic v2 / pydantic-settings · SQLAlchemy 2 (SQLite)
IA      : anthropic (Claude) — saída estruturada (Fase 2)
PDF     : pypdf + pdfplumber (fallback)  ·  Métricas: pandas
Frontend: React 18 + Vite + TypeScript · react-router-dom · lucide-react
Estilo  : CSS puro com design tokens (sem Tailwind)
Infra   : Docker (multi-stage) · um processo serve API + frontend
```

Não usar nesta fase: Celery, Redis, Postgres, Next.js, LangChain/LangGraph.
A IA é uma **chamada estruturada de turno único**, não um agente com loop de
ferramentas (seria o anti-padrão que o próprio case critica).

## 3. Arquitetura (alvo)

```
backend/app/
  main.py        FastAPI: monta /api + serve frontend/dist (SPA); cria DB no startup
  config.py      pydantic-settings (lê .env, defaults sãos)
  database.py    engine SQLAlchemy (SQLite) + Base + get_db
  models_db.py   modelos ORM (Fase 2: Vaga, Triagem, MetricRun)
  routers/       endpoints (/api/health agora; triagens/vagas/metrics na Fase 2)
  schemas/       Pydantic (Fase 2: JobProfile, ResumeSignals, TriageResult)
  pipeline/      ingest → redact(PII) → extract(Claude) → score(Python) → service
  evaluation/    camada de métricas (Fase 2)
frontend/src/    React (Sidebar, Topbar, páginas) + styles/ (design tokens SBF)
```

## 4. Regras de código

- **Idioma:** código, comentários e docstrings em **português**; nomes em
  `snake_case` (Python) / `camelCase` (TS) em português.
- **Type hints obrigatórios** em todo Python; **TypeScript estrito** no frontend.
- **Pydantic v2** para todo dado que cruza fronteira de módulo — nunca `dict` solto.
- **A nota é determinística:** `pipeline/score.py` recalcula tudo; a IA nunca
  decide a nota (Fase 2).
- **Rastreabilidade:** cada valor da triagem carrega `fonte` (evidência citada do
  CV) e `confianca`. Sem evidência → marca incerteza, não inventa.
- **Anti-viés / LGPD:** redigir PII **antes** de enviar à IA (Fase 2).
- **Erros nunca silenciados;** cada módulo tem fallback explícito.
- **Testes:** mudou `score`/`redact` → atualizar/adicionar teste. Rodar
  `make test` (deve ficar verde).

## 5. Design (frontend)

- Regras da marca em `Design System/gruposbf/design-system.html`; layout de
  referência em `Design System/saas_demo_1.html`.
- **Cores:** verde-escuro `#005E27` = **ação** (botões, texto branco);
  lime `#B5FF20` = **realce** (item ativo, destaques, texto escuro).
  Nunca lime como fundo de botão com texto branco (contraste).
- **Fontes:** Mona Sans (UI) + Writer (display), bundladas localmente.
- Tokens em `frontend/src/styles/tokens.css`. Tema claro por padrão.

## 6. Comandos

```bash
make install   # pip + npm
make build     # gera frontend/dist (necessário p/ rodar só com Python)
make run       # FastAPI servindo o dist → http://localhost:8000
make dev       # backend reload (:8000) + Vite (:5173)
make docker    # docker compose up --build
make test      # pytest
```

## 7. Regras absolutas

1. **NUNCA** deixar a nota final sair da IA — o Python recalcula (Fase 2).
2. **NUNCA** enviar PII à IA sem redação (Fase 2).
3. **NUNCA** passar `dict` solto entre módulos — usar schema Pydantic.
4. **NUNCA** silenciar exceções.
5. **SEMPRE** incluir `fonte` e `confianca` em cada valor extraído/calculado.
6. **SEMPRE** manter `frontend/dist` commitado (permite rodar sem Node).
