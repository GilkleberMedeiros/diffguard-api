"""
app/routers/health.py
~~~~~~~~~~~~~~~~~~~~~
Endpoint de health check: GET /health
"""

from fastapi import APIRouter

from app.models.response import HealthResponse

router = APIRouter(tags=["Saúde"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica se a API está operacional.",
)
async def health_check() -> HealthResponse:
    # TODO: Quando o worker backend for implementado, verificar sua
    # disponibilidade aqui (ex: ping no Redis para Celery).
    return HealthResponse(status="ok", workers="available")
