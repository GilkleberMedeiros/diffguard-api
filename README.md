# DiffGuard API

Serviço de análise inteligente de documentos e revisões via LLM.

## Stack

- **Python 3.12+**
- **FastAPI** — framework HTTP
- **LangChain** — pipelines de análise com LLM
- **pydantic-settings** — configuração via `.env`
- **uv** — gerenciador de dependências e ambientes

## Início rápido

```bash
# 1. Clone e entre na pasta
git clone <repo> && cd diffguard-api

# 2. Copie e preencha o .env
cp .env.example .env

# 3. Instale as dependências com uv
uv sync

# 4. Execute a API em modo desenvolvimento
uv run uvicorn app.main:app --reload
```

A documentação interativa estará disponível em:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Estrutura do projeto

```
app/
├── main.py          # Instância FastAPI + middlewares + routers
├── env.py           # Leitura do .env via pydantic-settings
├── config.py        # Configuração unificada (env + estáticas)
├── models/
│   ├── request.py   # AnalysisRequest, LLMConfig, AnalysisModule
│   └── response.py  # TaskResponse, resultados dos módulos, enums
├── routers/
│   ├── analysis.py  # POST/GET/DELETE /analysis
│   └── health.py    # GET /health
└── tasks/
    └── manager.py   # TaskManager em memória (ciclo de vida das tarefas)
```

## Próximos passos (a implementar)

- [ ] `app/tasks/runner.py` — orquestrador das chains LangChain
- [ ] `app/chains/contradiction.py` — detecção de contradições
- [ ] `app/chains/compliance.py` — análise de conformidade
- [ ] `app/chains/devil_advocate.py` — advogado do diabo
- [ ] `app/preprocessing/extractor.py` — extração de texto de PDF/DOCX
- [ ] Despacho do background task em `routers/analysis.py` (ver TODO)

Consulte `docs/spec.md` para a especificação completa.
