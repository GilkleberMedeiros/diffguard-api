"""
app/schemas/request.py
~~~~~~~~~~~~~~~~~~~~~
Schemas Pydantic de entrada (request body) da API.
"""

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class AnalysisModule(str, Enum):
  """Módulos de análise disponíveis."""

  CONTRADICTION = "contradiction"
  """Detecta contradições internas entre cláusulas alteradas e cláusulas intactas."""

  COMPLIANCE = "compliance"
  """Valida a conformidade do documento revisado com restrições fornecidas pelo usuário."""

  DEVIL_ADVOCATE = "devil_advocate"
  """Identifica pontos cegos — o que deveria ter sido alterado mas não foi."""


class LLMConfig(BaseModel):
  """Sobrescrita opcional das configurações do modelo de linguagem por requisição."""

  model: str | None = Field(
    default=None,
    description="Identificador do modelo a usar (ex: 'gpt-4o', 'gemini-2.0-flash').",
    examples=["gpt-4o", "gemini-2.0-flash"],
  )
  temperature: float | None = Field(
    default=None,
    ge=0.0,
    le=2.0,
    description="Temperatura de geração. Valores baixos tornam a saída mais determinística.",
  )
  max_tokens: int | None = Field(
    default=None,
    gt=0,
    description="Número máximo de tokens gerados na resposta do LLM.",
  )


class AnalysisRequest(BaseModel):
  """
  Corpo da requisição para criação de uma tarefa de análise.

  Os documentos devem ser enviados como texto puro (string). Suporte a
  envio de arquivos (PDF/DOCX) via multipart está previsto para versão futura.
  """

  base_document: str = Field(
    ...,
    min_length=1,
    description="Conteúdo do documento original em texto puro.",
  )
  revised_document: str = Field(
    ...,
    min_length=1,
    description="Conteúdo do documento revisado em texto puro.",
  )
  modules: list[AnalysisModule] = Field(
    ...,
    min_length=1,
    description=(
      "Módulos de análise a executar. Pelo menos um é obrigatório. "
      "Valores possíveis: 'contradiction', 'compliance', 'devil_advocate'."
    ),
    examples=[["contradiction", "devil_advocate"]],
  )
  constraints: list[str] | None = Field(
    default=None,
    min_length=1,
    description=(
      "Regras de conformidade em texto puro (lei, norma, política interna etc.). "
      "Obrigatório quando 'compliance' está presente em 'modules'."
    ),
  )
  language: str = Field(
    default="pt-BR",
    description="Idioma dos relatórios gerados (ex: 'pt-BR', 'en-US').",
    examples=["pt-BR", "en-US"],
  )
  llm_config: LLMConfig | None = Field(
    default=None,
    description="Sobrescrita opcional das configurações do LLM para esta requisição.",
  )

  @model_validator(mode="after")
  def _compliance_requires_constraints(self) -> "AnalysisRequest":
    if AnalysisModule.COMPLIANCE in self.modules and not self.constraints:
      raise ValueError(
        "O módulo 'compliance' requer o campo 'constraints' com as regras de conformidade."
      )
    return self

  @model_validator(mode="after")
  def _no_duplicate_modules(self) -> "AnalysisRequest":
    if len(self.modules) != len(set(self.modules)):
      raise ValueError("A lista 'modules' não pode conter módulos duplicados.")
    return self

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "base_document": "Cláusula 1: O prazo é de 12 meses...",
          "revised_document": "Cláusula 1: O prazo é de 36 meses...",
          "modules": ["contradiction", "devil_advocate"],
          "language": "pt-BR",
        }
      ]
    }
  }
