"""
app/tasks/manager.py
~~~~~~~~~~~~~~~~~~~~
Gerenciador em memória de tarefas de análise.

Responsabilidades:
- Criar, rastrear e cancelar tarefas.
- Expor métodos de atualização de estado para os workers (mark_running,
  mark_module_complete, mark_completed, mark_failed).
- Limpeza de tarefas expiradas via cleanup_expired().

O despacho e a execução das tarefas em background NÃO são responsabilidade
desta classe — ver app/routers/analysis.py para o ponto de integração.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.schemas.request import AnalysisRequest
from app.schemas.response import (
  AnalysisResults,
  TaskError,
  TaskProgress,
  TaskStatus,
)


@dataclass
class TaskRecord:
  """Estado completo de uma tarefa de análise mantido em memória."""

  task_id: str
  status: TaskStatus
  request: AnalysisRequest
  created_at: datetime
  completed_at: datetime | None = None
  results: AnalysisResults | None = None
  error: TaskError | None = None
  completed_modules: list[str] = field(default_factory=list)

  @property
  def pending_modules(self) -> list[str]:
    """Módulos ainda não concluídos."""
    return [m.value for m in self.request.modules if m.value not in self.completed_modules]

  @property
  def progress(self) -> TaskProgress:
    """Snapshot do progresso atual da tarefa."""
    return TaskProgress(
      completed_modules=list(self.completed_modules),
      pending_modules=self.pending_modules,
    )


class TaskManager:
  """
  Gerenciador de tarefas em memória, thread-safe via asyncio.Lock.

  Instancie uma única vez (singleton) e injete via Depends() nos routers.
  """

  def __init__(self) -> None:
    self._tasks: dict[str, TaskRecord] = {}
    self._lock = asyncio.Lock()

  # ── Criação ──────────────────────────────────────────────────────────── #

  async def create(self, request: AnalysisRequest) -> TaskRecord:
    """
    Cria e registra uma nova tarefa com status PENDING.

    Retorna o TaskRecord criado (com task_id gerado automaticamente).
    """
    task_id = str(uuid.uuid4())
    record = TaskRecord(
      task_id=task_id,
      status=TaskStatus.PENDING,
      request=request,
      created_at=datetime.now(tz=timezone.utc),
    )
    async with self._lock:
      self._tasks[task_id] = record
    return record

  # ── Leitura ──────────────────────────────────────────────────────────── #

  async def get(self, task_id: str) -> TaskRecord | None:
    """Retorna o registro de uma tarefa ou None se não encontrada."""
    async with self._lock:
      return self._tasks.get(task_id)

  # ── Atualização de estado (chamados pelo worker) ──────────────────────── #

  async def mark_running(self, task_id: str) -> bool:
    """
    Marca a tarefa como RUNNING.

    Deve ser chamado pelo worker logo ao iniciar o processamento.
    Retorna False se a tarefa não existir ou não estiver PENDING.
    """
    async with self._lock:
      task = self._tasks.get(task_id)
      if task is None or task.status != TaskStatus.PENDING:
        return False
      task.status = TaskStatus.RUNNING
      return True

  async def mark_module_complete(self, task_id: str, module: str) -> bool:
    """
    Registra um módulo como concluído (atualiza o progresso).

    Deve ser chamado pelo worker a cada módulo finalizado.
    Retorna False se a tarefa não existir.
    """
    async with self._lock:
      task = self._tasks.get(task_id)
      if task is None:
        return False
      if module not in task.completed_modules:
        task.completed_modules.append(module)
      return True

  async def mark_completed(self, task_id: str, results: AnalysisResults) -> bool:
    """
    Marca a tarefa como COMPLETED e persiste os resultados finais.

    Deve ser chamado pelo worker ao finalizar todos os módulos.
    Retorna False se a tarefa não existir ou não puder ser concluída.
    """
    async with self._lock:
      task = self._tasks.get(task_id)
      if task is None or task.status not in {TaskStatus.RUNNING, TaskStatus.PENDING}:
        return False
      task.status = TaskStatus.COMPLETED
      task.results = results
      task.completed_at = datetime.now(tz=timezone.utc)
      return True

  async def mark_failed(self, task_id: str, error: TaskError) -> bool:
    """
    Marca a tarefa como FAILED com a descrição do erro.

    Deve ser chamado pelo worker em caso de falha não-recuperável.
    Retorna False se a tarefa não existir ou já tiver sido cancelada.
    """
    async with self._lock:
      task = self._tasks.get(task_id)
      if task is None or task.status == TaskStatus.CANCELLED:
        return False
      task.status = TaskStatus.FAILED
      task.error = error
      task.completed_at = datetime.now(tz=timezone.utc)
      return True

  # ── Cancelamento ─────────────────────────────────────────────────────── #

  async def cancel(self, task_id: str) -> bool:
    """
    Tenta cancelar uma tarefa PENDING ou RUNNING.

    Retorna True se o cancelamento foi registrado com sucesso.
    Retorna False se a tarefa já estiver em estado terminal
    (COMPLETED, FAILED ou CANCELLED) — o router deve responder 409.
    """
    async with self._lock:
      task = self._tasks.get(task_id)
      if task is None:
        return False
      if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
        return False
      task.status = TaskStatus.CANCELLED
      task.completed_at = datetime.now(tz=timezone.utc)
      return True

  # ── Limpeza ──────────────────────────────────────────────────────────── #

  async def cleanup_expired(self, ttl_seconds: int) -> int:
    """
    Remove tarefas em estado terminal que ultrapassaram o TTL.

    Deve ser agendado periodicamente pelo sistema de background tasks
    (ex: a cada hora). Retorna o número de tarefas removidas.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=ttl_seconds)
    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    to_delete: list[str] = []

    async with self._lock:
      for task_id, task in self._tasks.items():
        if task.status in terminal_statuses and task.created_at < cutoff:
          to_delete.append(task_id)
      for task_id in to_delete:
        del self._tasks[task_id]

    return len(to_delete)


# ── Singleton e injeção de dependência ───────────────────────────────────── #

_task_manager = TaskManager()


def get_task_manager() -> TaskManager:
  """Dependência FastAPI — injeta o TaskManager singleton via Depends()."""
  return _task_manager
