"""
app/config.py
~~~~~~~~~~~~~
Configuração unificada da aplicação.

Combina as variáveis de ambiente (via EnvSettings) com constantes
estáticas definidas no código. Este é o único ponto de verdade para
qualquer configuração consumida pelos módulos da aplicação.

Uso:
  from app.config import config

  config.API_TITLE
  config.env.llm_model
  config.max_document_size_bytes
"""

from app.env import EnvSettings, env_settings


class _Config:
  # ── Referência ao ambiente ────────────────────────────────────────────── #
  env: EnvSettings = env_settings

  # ── Metadados da API ─────────────────────────────────────────────────── #
  API_TITLE: str = "DiffGuard API"
  API_VERSION: str = "1.0.0"
  API_DESCRIPTION: str = (
    "Serviço de análise inteligente de documentos e revisões. "
    "Detecta contradições, verifica conformidade com restrições externas "
    "e identifica pontos cegos deixados pela revisão."
  )
  API_CONTACT: dict[str, str] = {
    "name": "DiffGuard",
    "url": "https://github.com/seu-usuario/diffguard-api",
  }
  API_LICENSE: dict[str, str] = {
    "name": "MIT",
  }

  # ── Módulos de análise disponíveis ───────────────────────────────────── #
  AVAILABLE_MODULES: frozenset[str] = frozenset(
    {"contradiction", "compliance", "devil_advocate"}
  )

  # ── Provedores de LLM suportados ─────────────────────────────────────── #
  SUPPORTED_LLM_PROVIDERS: frozenset[str] = frozenset({"openai", "google", "ollama"})

  # ── Backends de worker suportados ────────────────────────────────────── #
  SUPPORTED_WORKER_BACKENDS: frozenset[str] = frozenset({"background", "celery"})

  # ── Tipos MIME aceitos para upload de documentos ──────────────────────── #
  SUPPORTED_MIME_TYPES: frozenset[str] = frozenset(
    {
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
      "text/markdown",
    }
  )

  # ── Logging ──────────────────────────────────────────────────────────── #
  LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
  LOG_DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"

  # ── Limites derivados do ambiente ─────────────────────────────────────── #
  @property
  def max_document_size_bytes(self) -> int:
    """Tamanho máximo de documento em bytes (derivado de MAX_DOCUMENT_SIZE_KB)."""
    return self.env.max_document_size_kb * 1024


# Singleton — importar `config` onde precisar de configurações
config = _Config()
