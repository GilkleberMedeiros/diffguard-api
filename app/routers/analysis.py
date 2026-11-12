"""
app/routers/analysis.py
~~~~~~~~~~~~~~~~~~~~~~~
Endpoints de análise:
  POST   /analysis           — cria tarefa
  GET    /analysis/{task_id} — consulta status/resultado
  DELETE /analysis/{task_id} — cancela tarefa
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.schemas.request import AnalysisRequest
from app.schemas.response import (
  TaskCreatedResponse,
  TaskResponse,
  TaskStatus,
)
from app.tasks.manager import TaskManager, get_task_manager

router = APIRouter(prefix="/analysis", tags=["Análise"])


@router.post(
  "",
  status_code=status.HTTP_202_ACCEPTED,
  response_model=TaskCreatedResponse,
  summary="Criar tarefa de análise",
  description=(
    "Recebe os documentos e a configuração de análise, registra a tarefa "
    "e retorna imediatamente com o ID e a URL de polling. "
    "O processamento é realizado de forma assíncrona no backend."
  ),
)
async def create_analysis(
  request: Request,
  body: AnalysisRequest,
  background_tasks: BackgroundTasks,
  task_manager: TaskManager = Depends(get_task_manager),
) -> TaskCreatedResponse:
  record = await task_manager.create(body)

  # ------------------------------------------------------------------ #
  # TODO: despache a tarefa de background aqui.                         #
  #                                                                     #
  # Opção A — FastAPI BackgroundTasks (sem dependências extras):        #
  #   from app.tasks.runner import run_analysis                         #
  #   background_tasks.add_task(run_analysis, record.task_id, body)    #
  #                                                                     #
  # Opção B — Celery:                                                   #
  #   from app.tasks.runner import run_analysis_task                   #
  #   run_analysis_task.delay(record.task_id, body.model_dump())       #
  # ------------------------------------------------------------------ #

  base_url = str(request.base_url).rstrip("/")
  return TaskCreatedResponse(
    task_id=record.task_id,
    status=record.status,
    created_at=record.created_at,
    poll_url=f"{base_url}/analysis/{record.task_id}",
  )


@router.get(
  "/{task_id}",
  response_model=TaskResponse,
  summary="Consultar tarefa",
  description=(
    "Retorna o status atual da tarefa e, quando concluída (status='completed'), "
    "os resultados dos módulos executados."
  ),
  responses={
    404: {"description": "Tarefa não encontrada"},
  },
)
async def get_analysis(
  task_id: str,
  task_manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
  record = await task_manager.get(task_id)
  if record is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail={"code": "TASK_NOT_FOUND", "message": f"Tarefa '{task_id}' não encontrada."},
    )

  return TaskResponse(
    task_id=record.task_id,
    status=record.status,
    created_at=record.created_at,
    completed_at=record.completed_at,
    progress=record.progress if record.status == TaskStatus.RUNNING else None,
    results=record.results,
    error=record.error,
  )


@router.delete(
  "/{task_id}",
  response_model=TaskResponse,
  summary="Cancelar tarefa",
  description="Cancela uma tarefa com status 'pending' ou 'running'.",
  responses={
    404: {"description": "Tarefa não encontrada"},
    409: {"description": "Tarefa já concluída, cancelada ou com falha"},
  },
)
async def cancel_analysis(
  task_id: str,
  task_manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
  record = await task_manager.get(task_id)
  if record is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail={"code": "TASK_NOT_FOUND", "message": f"Tarefa '{task_id}' não encontrada."},
    )

  cancelled = await task_manager.cancel(task_id)
  if not cancelled:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail={
        "code": "TASK_NOT_CANCELLABLE",
        "message": f"Tarefa '{task_id}' já está em estado terminal e não pode ser cancelada.",
      },
    )

  # Recarrega o registro com o estado atualizado
  record = await task_manager.get(task_id)
  return TaskResponse(
    task_id=record.task_id,
    status=record.status,
    created_at=record.created_at,
    completed_at=record.completed_at,
  )
