"""
app/env.py
~~~~~~~~~~
Carrega e valida as variáveis de ambiente do arquivo .env.
Apenas leitura — sem lógica de negócio.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """
    Mapeamento direto entre variáveis de ambiente e atributos Python.

    Usa pydantic-settings para leitura automática do .env e validação
    de tipos. Os nomes das variáveis de ambiente são os nomes dos campos
    em UPPER_SNAKE_CASE (padrão do pydantic-settings).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────── #
    llm_provider: str = Field(default="openai", description="Provedor do LLM (openai | google | ollama)")
    llm_model: str = Field(default="gpt-4o", description="Identificador do modelo")
    llm_api_key: str | None = Field(default=None, description="Chave de API do provedor")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Temperatura de geração")
    llm_max_tokens: int = Field(default=4096, gt=0, description="Máximo de tokens por resposta")

    # ── Limites ───────────────────────────────────────────────────────────── #
    max_document_size_kb: int = Field(default=2048, gt=0, description="Tamanho máximo de documento (KB)")
    task_ttl_seconds: int = Field(default=3600, gt=0, description="TTL das tarefas na memória (s)")

    # ── Worker ────────────────────────────────────────────────────────────── #
    worker_backend: str = Field(default="background", description="Backend de tarefas (background | celery)")
    celery_broker_url: str | None = Field(default=None, description="URL do broker Celery")

    # ── Aplicação ─────────────────────────────────────────────────────────── #
    log_level: str = Field(default="INFO", description="Nível de log (DEBUG | INFO | WARNING | ERROR)")
    default_language: str = Field(default="pt-BR", description="Idioma padrão dos relatórios")


# Singleton — importar `env_settings` onde precisar das variáveis de ambiente
env_settings = EnvSettings()
