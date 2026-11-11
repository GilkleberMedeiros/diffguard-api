# DiffGuard API — Documento de Especificação

> **Versão:** 1.0.0  
> **Data:** 2026-11-11  
> **Stack:** Python · FastAPI · LangChain

---

## 1. Visão Geral

A **DiffGuard API** é um serviço de análise inteligente de documentos e suas revisões. Dado um documento original e uma versão alterada, a API executa análises profundas de forma assíncrona, retornando relatórios estruturados sobre contradições internas, conformidade com regras externas e pontos cegos deixados pela revisão.

O foco principal é a análise de **contratos jurídicos**, mas o serviço é genérico o suficiente para atender documentos de especificação técnica, normas regulatórias, TCCs e qualquer documento que evolua por versões.

A API é **stateless**: nenhum estado de conversa ou resultado anterior é armazenado entre requisições.

---

## 2. Arquitetura Geral

```
Cliente
  │
  ▼
POST /analysis          ← recebe documentos + configuração
  │
  ▼
Fila de tarefas         ← tarefa assíncrona criada (Celery ou asyncio BackgroundTask)
  │
  ▼
Worker LangChain        ← pipeline de análise por Chain/Agent
  │
  ▼
GET /analysis/{id}      ← cliente consulta o resultado
```

### 2.1 Componentes Principais

| Componente | Responsabilidade |
|---|---|
| **FastAPI App** | Roteamento HTTP, validação de entrada, serialização de resposta |
| **Task Manager** | Enfileiramento e rastreamento de tarefas assíncronas |
| **LangChain Pipelines** | Chains especializadas para cada módulo de análise |
| **LLM Backend** | Modelo de linguagem configurável (OpenAI, Gemini, Ollama etc.) |

---

## 3. Domínio e Conceitos

| Termo | Definição |
|---|---|
| **Documento Base** | Versão original do documento (antes das alterações) |
| **Documento Revisado** | Versão atualizada do documento (após as alterações) |
| **Diff Semântico** | Conjunto de mudanças identificadas entre as duas versões pelo próprio modelo, além do diff textual bruto |
| **Restrição** | Regra externa fornecida pelo usuário que o documento revisado deve obedecer |
| **Relatório** | Saída estruturada de um módulo de análise |

---

## 4. Módulos de Análise

### 4.1 Detecção de Contradições (`contradiction`)

Varre o documento revisado em busca de conflitos **internos** gerados pelas alterações. O foco não é resumir o documento, mas cruzar sistematicamente as cláusulas ou seções alteradas com aquelas que permaneceram intactas, identificando onde uma mudança anula, contradiz ou cria ambiguidade com outra parte do texto que não foi tocada.

**Comportamento:**
- Identifica cada par de trechos conflitantes (trecho A alterado × trecho Z intacto).
- Para cada conflito, descreve a natureza da contradição e sua gravidade.
- Referencia os trechos pelo número de cláusula, seção ou parágrafo quando disponível, ou por localização aproximada (ex.: página, posição relativa).

**Saída por item:**
```json
{
  "conflict_id": "c1",
  "severity": "high | medium | low",
  "changed_section": "Cláusula 3.2",
  "intact_section": "Cláusula 11.4",
  "description": "A nova redação de 3.2 elimina a multa por rescisão, mas 11.4 ainda a referencia como vigente.",
  "recommendation": "Atualizar ou revogar explicitamente a Cláusula 11.4."
}
```

---

### 4.2 Análise de Conformidade com Restrições (`compliance`)

Valida se o documento revisado — e as mudanças introduzidas — estão em conformidade com um conjunto de regras fornecidas pelo usuário. As regras podem ser enviadas como texto livre ou como um documento separado (ex.: lei, norma técnica, política interna).

**Comportamento:**
- Cada restrição é avaliada individualmente contra o documento revisado.
- O resultado indica se a restrição é atendida, violada ou inconclusiva.
- Violações apontam o trecho do documento responsável pelo não-atendimento.

**Saída por item:**
```json
{
  "rule_id": "r1",
  "rule_summary": "O contrato não pode ter prazo superior a 24 meses sem cláusula de renegociação.",
  "status": "violated | compliant | inconclusive",
  "offending_section": "Cláusula 2.1",
  "explanation": "O prazo definido é de 36 meses sem qualquer menção a renegociação.",
  "recommendation": "Incluir cláusula de renegociação obrigatória ao atingir 24 meses."
}
```

---

### 4.3 Advogado do Diabo (`devil_advocate`)

Gera um relatório de **pontos cegos** da revisão: o que deveria ter sido alterado mas não foi. Opera a partir da perspectiva de quem revisa criticamente a revisão, listando omissões e inconsistências de escopo.

**Comportamento:**
- Analisa o conjunto de mudanças realizadas e infere o **objetivo aparente** da revisão.
- A partir desse objetivo, identifica seções que, logicamente, também deveriam ter sido alteradas mas permaneceram inalteradas.
- Pode sinalizar também cláusulas ou definições que ficaram desatualizadas em relação ao novo contexto criado pelas alterações.

**Saída por item:**
```json
{
  "blind_spot_id": "b1",
  "severity": "high | medium | low",
  "section": "Cláusula 7.3",
  "reason": "A alteração em 2.1 muda o objeto do contrato de 'serviços de TI' para 'serviços de consultoria', mas 7.3 ainda lista obrigações técnicas de TI como responsabilidade do contratado.",
  "suggestion": "Revisar 7.3 para refletir as obrigações de consultoria."
}
```

---

## 5. API — Endpoints

### `POST /analysis`

Cria uma nova tarefa de análise. Retorna imediatamente com o ID da tarefa.

**Content-Type:** `multipart/form-data` ou `application/json`

#### Campos do corpo da requisição

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `base_document` | `file` ou `string` | Sim | Documento original. Aceita `.pdf`, `.docx` ou texto puro |
| `revised_document` | `file` ou `string` | Sim | Documento revisado |
| `modules` | `array[string]` | Sim | Módulos a executar: `contradiction`, `compliance`, `devil_advocate` |
| `constraints` | `file` ou `string` | Não | Regras de conformidade (obrigatório se `compliance` estiver em `modules`) |
| `language` | `string` | Não | Idioma dos relatórios. Padrão: `"pt-BR"` |
| `llm_config` | `object` | Não | Sobrescreve configurações do LLM (model, temperature etc.) |

#### Exemplo de requisição (JSON)

```json
{
  "base_document": "...<texto do contrato original>...",
  "revised_document": "...<texto do contrato revisado>...",
  "modules": ["contradiction", "devil_advocate"],
  "language": "pt-BR"
}
```

#### Resposta `202 Accepted`

```json
{
  "task_id": "a3f9c1d2-...",
  "status": "pending",
  "created_at": "2026-11-11T15:30:00Z",
  "poll_url": "/analysis/a3f9c1d2-..."
}
```

---

### `GET /analysis/{task_id}`

Consulta o status e, quando concluída, o resultado de uma tarefa de análise.

#### Resposta — tarefa em andamento `200 OK`

```json
{
  "task_id": "a3f9c1d2-...",
  "status": "running",
  "progress": {
    "completed_modules": ["contradiction"],
    "pending_modules": ["devil_advocate"]
  }
}
```

#### Resposta — tarefa concluída `200 OK`

```json
{
  "task_id": "a3f9c1d2-...",
  "status": "completed",
  "created_at": "2026-11-11T15:30:00Z",
  "completed_at": "2026-11-11T15:31:45Z",
  "results": {
    "contradiction": {
      "total_conflicts": 2,
      "items": [ { "conflict_id": "c1", "..." : "..." } ]
    },
    "devil_advocate": {
      "total_blind_spots": 3,
      "items": [ { "blind_spot_id": "b1", "..." : "..." } ]
    }
  }
}
```

#### Resposta — tarefa com erro `200 OK`

```json
{
  "task_id": "a3f9c1d2-...",
  "status": "failed",
  "error": {
    "code": "DOCUMENT_PARSE_ERROR",
    "message": "Não foi possível extrair texto do arquivo enviado."
  }
}
```

---

### `DELETE /analysis/{task_id}`

Cancela uma tarefa pendente ou em execução.

#### Resposta `200 OK`

```json
{
  "task_id": "a3f9c1d2-...",
  "status": "cancelled"
}
```

---

### `GET /health`

Verifica se a API e seus workers estão operacionais.

#### Resposta `200 OK`

```json
{
  "status": "ok",
  "workers": "available"
}
```

---

## 6. Modelos de Dados

### `AnalysisRequest`

```python
class AnalysisRequest(BaseModel):
    base_document: str
    revised_document: str
    modules: list[Literal["contradiction", "compliance", "devil_advocate"]]
    constraints: str | None = None
    language: str = "pt-BR"
    llm_config: LLMConfig | None = None
```

### `LLMConfig`

```python
class LLMConfig(BaseModel):
    model: str | None = None        # ex: "gpt-4o", "gemini-2.0-flash"
    temperature: float | None = None
    max_tokens: int | None = None
```

### `TaskStatus`

```python
class TaskStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"
```

---

## 7. Processamento Assíncrono

As tarefas são enfileiradas no momento da requisição e processadas por workers independentes, mantendo o endpoint `POST /analysis` não-bloqueante.

### Fluxo de execução

```
1. POST /analysis
      └─► valida entrada
      └─► cria task_id (UUID)
      └─► enfileira tarefa → retorna 202

2. Worker recebe tarefa
      └─► extrai/normaliza texto dos documentos
      └─► computa diff textual bruto (unified diff)
      └─► executa módulos solicitados em paralelo (quando possível)
            ├─ ContradictionChain
            ├─ ComplianceChain
            └─ DevilAdvocateChain
      └─► agrega resultados
      └─► atualiza status → "completed" ou "failed"

3. GET /analysis/{task_id}
      └─► retorna status atual + resultados (se concluído)
```

### Estratégia de implementação

- **Primeira iteração:** `BackgroundTasks` do FastAPI (sem dependência externa, adequado para workloads moderados).
- **Escala:** migração transparente para **Celery + Redis** ou **ARQ** sem alteração de contrato da API.
- Os resultados intermediários/finais são mantidos em memória ou em um store efêmero (Redis, SQLite em disco) **apenas durante o ciclo de vida da tarefa**. Não há persistência de longo prazo.

---

## 8. Pipeline LangChain

Cada módulo de análise é implementado como uma **Chain** independente do LangChain.

```
DocumentPreprocessor
      │
      ▼
DiffExtractor           ← diff textual + detecção de seções alteradas
      │
      ├──► ContradictionChain
      │         └─ prompt: varredura cruzada de cláusulas
      │
      ├──► ComplianceChain
      │         └─ prompt: avaliação regra por regra
      │
      └──► DevilAdvocateChain
                └─ prompt: inferência de objetivo + gap analysis
```

### Considerações de prompt

- Todos os prompts são parametrizados pelo idioma (`language`).
- O documento é fragmentado em chunks com overlap para lidar com contextos longos (strategy: `RecursiveCharacterTextSplitter`).
- Módulos independentes (`contradiction` e `devil_advocate`) rodam em paralelo via `asyncio.gather`.
- `compliance` depende das restrições fornecidas pelo usuário; quando ausentes e o módulo é solicitado, a API retorna `400 Bad Request`.

---

## 9. Tratamento de Erros

| Código HTTP | Código interno | Situação |
|---|---|---|
| `400` | `MISSING_CONSTRAINTS` | Módulo `compliance` solicitado sem restrições |
| `400` | `INVALID_MODULE` | Nome de módulo desconhecido em `modules` |
| `400` | `DOCUMENT_TOO_LARGE` | Documento excede o limite configurado |
| `404` | `TASK_NOT_FOUND` | `task_id` inexistente |
| `409` | `TASK_NOT_CANCELLABLE` | Tarefa já concluída ou cancelada |
| `422` | _(gerado pelo FastAPI)_ | Falha de validação de schema |
| `500` | `LLM_ERROR` | Falha na chamada ao modelo de linguagem |
| `500` | `DOCUMENT_PARSE_ERROR` | Falha na extração de texto do arquivo |

---

## 10. Estrutura de Pastas do Projeto

```
diffguard-api/
├── docs/
│   └── spec.md                  ← este documento
├── app/
│   ├── main.py                  ← instância FastAPI, rotas
│   ├── config.py                ← variáveis de ambiente (pydantic-settings)
│   ├── models/
│   │   ├── request.py           ← AnalysisRequest, LLMConfig
│   │   └── response.py          ← TaskResponse, ResultItem, etc.
│   ├── routers/
│   │   └── analysis.py          ← endpoints /analysis
│   ├── tasks/
│   │   ├── manager.py           ← criação, rastreamento e cancelamento de tarefas
│   │   └── runner.py            ← orquestração dos módulos de análise
│   ├── chains/
│   │   ├── base.py              ← classe base e utilitários compartilhados
│   │   ├── contradiction.py     ← ContradictionChain
│   │   ├── compliance.py        ← ComplianceChain
│   │   └── devil_advocate.py    ← DevilAdvocateChain
│   ├── preprocessing/
│   │   ├── extractor.py         ← extração de texto de PDF/DOCX
│   │   └── differ.py           ← diff textual e segmentação de seções
│   └── prompts/
│       ├── contradiction.txt
│       ├── compliance.txt
│       └── devil_advocate.txt
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 11. Configuração e Variáveis de Ambiente

```dotenv
# LLM
LLM_PROVIDER=openai          # openai | google | ollama
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Limites
MAX_DOCUMENT_SIZE_KB=2048
TASK_TTL_SECONDS=3600        # tempo máximo de vida de uma tarefa na memória

# Worker
WORKER_BACKEND=background    # background | celery
CELERY_BROKER_URL=redis://localhost:6379/0   # usado apenas se backend=celery

# App
LOG_LEVEL=INFO
DEFAULT_LANGUAGE=pt-BR
```

---

## 12. Formato de Entrada dos Documentos

| Formato | Suporte | Observação |
|---|---|---|
| Texto puro (`string`) | ✅ | Enviado diretamente no JSON |
| PDF (`.pdf`) | ✅ | Extração via `pdfminer.six` ou `pymupdf` |
| Word (`.docx`) | ✅ | Extração via `python-docx` |
| Markdown (`.md`) | ✅ | Tratado como texto puro |
| HTML | ⚠️ Futuro | Não incluso no escopo inicial |

---

## 13. Escopo e Limitações

**Incluso no escopo:**
- Análise de dois documentos (base e revisado) por requisição.
- Três módulos de análise independentes e combináveis.
- Processamento assíncrono com polling de status.
- Suporte a múltiplos provedores de LLM via configuração.
- Extração de texto de PDF e DOCX.

**Fora do escopo:**
- Autenticação e controle de acesso.
- Histórico ou persistência de análises anteriores.
- Interface de usuário (front-end).
- Webhooks ou notificações push ao término da tarefa (versão futura).
- Comparação de mais de duas versões simultaneamente.
