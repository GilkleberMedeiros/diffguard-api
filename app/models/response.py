"""
app/models/response.py
~~~~~~~~~~~~~~~~~~~~~~
Modelos Pydantic de saída (response body) da API.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────── #


class TaskStatus(str, Enum):
    """Ciclo de vida de uma tarefa de análise."""

    PENDING = "pending"
    """Tarefa criada, aguardando despacho para o worker."""

    RUNNING = "running"
    """Tarefa em execução no worker."""

    COMPLETED = "completed"
    """Tarefa concluída com sucesso. Resultados disponíveis."""

    FAILED = "failed"
    """Tarefa encerrada com erro. Ver campo 'error'."""

    CANCELLED = "cancelled"
    """Tarefa cancelada pelo cliente."""


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    VIOLATED = "violated"
    INCONCLUSIVE = "inconclusive"


# ── Resultado: Detecção de Contradições ───────────────────────────────────── #


class ConflictItem(BaseModel):
    """Um par de trechos em conflito identificado pelo módulo 'contradiction'."""

    conflict_id: str = Field(description="Identificador único do conflito (ex: 'c1').")
    severity: Severity = Field(description="Gravidade do conflito.")
    changed_section: str = Field(description="Referência à seção alterada que originou o conflito.")
    intact_section: str = Field(description="Referência à seção intacta que entra em conflito.")
    description: str = Field(description="Descrição da natureza da contradição.")
    recommendation: str = Field(description="Sugestão de resolução do conflito.")


class ContradictionResult(BaseModel):
    """Saída completa do módulo 'contradiction'."""

    total_conflicts: int = Field(ge=0)
    items: list[ConflictItem] = Field(default_factory=list)


# ── Resultado: Conformidade com Restrições ────────────────────────────────── #


class ComplianceItem(BaseModel):
    """Resultado da avaliação de uma regra de conformidade individual."""

    rule_id: str = Field(description="Identificador único da regra (ex: 'r1').")
    rule_summary: str = Field(description="Resumo da regra avaliada.")
    status: ComplianceStatus = Field(description="Resultado da avaliação.")
    offending_section: str | None = Field(
        default=None,
        description="Referência à seção que viola a regra (quando status='violated').",
    )
    explanation: str = Field(description="Explicação do resultado da avaliação.")
    recommendation: str | None = Field(
        default=None,
        description="Sugestão de correção (quando status='violated').",
    )


class ComplianceResult(BaseModel):
    """Saída completa do módulo 'compliance'."""

    total_rules: int = Field(ge=0)
    total_violations: int = Field(ge=0)
    items: list[ComplianceItem] = Field(default_factory=list)


# ── Resultado: Advogado do Diabo ──────────────────────────────────────────── #


class BlindSpotItem(BaseModel):
    """Um ponto cego identificado pelo módulo 'devil_advocate'."""

    blind_spot_id: str = Field(description="Identificador único do ponto cego (ex: 'b1').")
    severity: Severity = Field(description="Gravidade do ponto cego.")
    section: str = Field(description="Referência à seção que deveria ter sido revisada.")
    reason: str = Field(description="Motivo pelo qual a seção deveria ter sido alterada.")
    suggestion: str = Field(description="Sugestão de alteração.")


class DevilAdvocateResult(BaseModel):
    """Saída completa do módulo 'devil_advocate'."""

    total_blind_spots: int = Field(ge=0)
    items: list[BlindSpotItem] = Field(default_factory=list)


# ── Resultados Agregados ──────────────────────────────────────────────────── #


class AnalysisResults(BaseModel):
    """Contêiner com os resultados de todos os módulos executados."""

    contradiction: ContradictionResult | None = None
    compliance: ComplianceResult | None = None
    devil_advocate: DevilAdvocateResult | None = None


# ── Progresso ─────────────────────────────────────────────────────────────── #


class TaskProgress(BaseModel):
    """Progresso de execução de uma tarefa com status RUNNING."""

    completed_modules: list[str] = Field(default_factory=list)
    pending_modules: list[str] = Field(default_factory=list)


# ── Erro ──────────────────────────────────────────────────────────────────── #


class TaskError(BaseModel):
    """Descrição estruturada de um erro de execução."""

    code: str = Field(description="Código interno do erro (ex: 'LLM_ERROR').")
    message: str = Field(description="Mensagem legível descrevendo o erro.")


# ── Resposta de Criação (202) ─────────────────────────────────────────────── #


class TaskCreatedResponse(BaseModel):
    """Resposta retornada imediatamente após a criação de uma tarefa (HTTP 202)."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
    poll_url: str = Field(description="URL para consultar o status/resultado da tarefa.")


# ── Resposta de Consulta ──────────────────────────────────────────────────── #


class TaskResponse(BaseModel):
    """Resposta completa de consulta de uma tarefa (GET /analysis/{task_id})."""

    task_id: str
    status: TaskStatus
    created_at: datetime
    completed_at: datetime | None = None
    progress: TaskProgress | None = Field(
        default=None,
        description="Disponível apenas quando status='running'.",
    )
    results: AnalysisResults | None = Field(
        default=None,
        description="Disponível apenas quando status='completed'.",
    )
    error: TaskError | None = Field(
        default=None,
        description="Disponível apenas quando status='failed'.",
    )


# ── Health ────────────────────────────────────────────────────────────────── #


class HealthResponse(BaseModel):
    status: str = Field(description="Status geral da API ('ok' | 'degraded').")
    workers: str = Field(description="Status do backend de workers ('available' | 'unavailable').")
