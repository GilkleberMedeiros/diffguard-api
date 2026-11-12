"""
app/main.py
~~~~~~~~~~~
Ponto de entrada da aplicação FastAPI.

Para executar em desenvolvimento:
  uvicorn app.main:app --reload

Para executar em produção:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.routers import analysis, health


# ── Logging ───────────────────────────────────────────────────────────────── #

logging.basicConfig(
  level=config.env.log_level.upper(),
  format=config.LOG_FORMAT,
  datefmt=config.LOG_DATE_FORMAT,
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────── #


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
  """Eventos de startup e shutdown da aplicação."""
  logger.info("DiffGuard API iniciando (worker_backend=%s)", config.env.worker_backend)

  # TODO: Inicializações de startup podem ser adicionadas aqui.
  # Exemplos:
  #   - Pré-carregar o modelo / embeddings
  #   - Verificar conexão com o broker Celery/Redis
  #   - Agendar tarefa periódica de cleanup (task_manager.cleanup_expired)

  yield

  logger.info("DiffGuard API encerrando.")


# ── Aplicação ─────────────────────────────────────────────────────────────── #


app = FastAPI(
  title=config.API_TITLE,
  version=config.API_VERSION,
  description=config.API_DESCRIPTION,
  contact=config.API_CONTACT,
  license_info=config.API_LICENSE,
  lifespan=lifespan,
)

# ── Middlewares ───────────────────────────────────────────────────────────── #

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────── #

app.include_router(health.router)
app.include_router(analysis.router)
