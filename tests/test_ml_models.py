from unittest.mock import MagicMock, patch
import pytest

from app.services.ml_models import MLModelsService


class TestMLModelsService:
  """Testes unitários para o serviço MLModelsService."""

  @patch("app.services.ml_models.ChatGoogleGenerativeAI")
  def test_load_llm_model_google(self, mock_google_ai):
    """Testa carregamento direto do modelo Google GenAI."""
    mock_instance = MagicMock()
    mock_google_ai.return_value = mock_instance

    result = MLModelsService._load_llm_model_google(
      model="gemini-2.0-flash",
      api_key="fake-key",
      temperature=0.2,
      max_output_tokens=1024,
    )

    mock_google_ai.assert_called_once_with(
      model="gemini-2.0-flash",
      api_key="fake-key",
      temperature=0.2,
      max_output_tokens=1024,
    )
    assert result == mock_instance

  @patch("app.services.ml_models.ChatOpenAI")
  def test_load_llm_model_openai(self, mock_chat_openai):
    """Testa carregamento direto do modelo OpenAI com mapeamento de max_output_tokens."""
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    result = MLModelsService._load_llm_model_openai(
      model="gpt-4o",
      api_key="sk-test",
      temperature=0.5,
      max_output_tokens=2048,
    )

    mock_chat_openai.assert_called_once_with(
      model="gpt-4o",
      api_key="sk-test",
      temperature=0.5,
      max_completion_tokens=2048,
    )
    assert result == mock_instance

  @patch("app.services.ml_models.ChatOpenAI")
  def test_load_llm_model_openai_without_max_output_tokens(self, mock_chat_openai):
    """Testa OpenAI sem max_output_tokens fornecido."""
    MLModelsService._load_llm_model_openai(model="gpt-4o", api_key="sk-test")
    mock_chat_openai.assert_called_once_with(model="gpt-4o", api_key="sk-test")

  @patch("app.services.ml_models.ChatOllama")
  def test_load_llm_model_ollama(self, mock_chat_ollama):
    """Testa carregamento direto do modelo Ollama (removendo api_key e mapeando num_predict)."""
    mock_instance = MagicMock()
    mock_chat_ollama.return_value = mock_instance

    result = MLModelsService._load_llm_model_ollama(
      model="llama3",
      api_key="fake-api-key",
      temperature=0.7,
      max_output_tokens=512,
    )

    mock_chat_ollama.assert_called_once_with(
      model="llama3",
      temperature=0.7,
      num_predict=512,
    )
    assert result == mock_instance

  @patch("app.services.ml_models.config")
  @patch.object(MLModelsService, "_load_llm_model_google")
  def test_get_main_llm_model_google(self, mock_load_google, mock_config):
    """Testa get_main_llm_model quando provider é google."""
    mock_config.env.llm_provider = "google"
    mock_config.env.llm_model = "gemini-1.5-pro"
    mock_config.env.llm_api_key = "test-google-key"
    mock_config.env.llm_temperature = 0.3
    mock_config.env.llm_max_tokens = 1000

    mock_llm_instance = MagicMock()
    mock_load_google.return_value = mock_llm_instance

    result = MLModelsService.get_main_llm_model()

    mock_load_google.assert_called_once_with(
      "gemini-1.5-pro",
      api_key="test-google-key",
      temperature=0.3,
      max_output_tokens=1000,
    )
    assert result == mock_llm_instance

  @patch("app.services.ml_models.config")
  @patch.object(MLModelsService, "_load_llm_model_openai")
  def test_get_main_llm_model_openai(self, mock_load_openai, mock_config):
    """Testa get_main_llm_model quando provider é openai."""
    mock_config.env.llm_provider = "openai"
    mock_config.env.llm_model = "gpt-4o-mini"
    mock_config.env.llm_api_key = "test-openai-key"
    mock_config.env.llm_temperature = 0.1
    mock_config.env.llm_max_tokens = 2000

    mock_llm_instance = MagicMock()
    mock_load_openai.return_value = mock_llm_instance

    result = MLModelsService.get_main_llm_model()

    mock_load_openai.assert_called_once_with(
      "gpt-4o-mini",
      api_key="test-openai-key",
      temperature=0.1,
      max_output_tokens=2000,
    )
    assert result == mock_llm_instance

  @patch("app.services.ml_models.config")
  @patch.object(MLModelsService, "_load_llm_model_ollama")
  def test_get_main_llm_model_ollama(self, mock_load_ollama, mock_config):
    """Testa get_main_llm_model quando provider é ollama."""
    mock_config.env.llm_provider = "ollama"
    mock_config.env.llm_model = "mistral"
    mock_config.env.llm_api_key = None
    mock_config.env.llm_temperature = 0.0
    mock_config.env.llm_max_tokens = 4096

    mock_llm_instance = MagicMock()
    mock_load_ollama.return_value = mock_llm_instance

    result = MLModelsService.get_main_llm_model()

    mock_load_ollama.assert_called_once_with(
      "mistral",
      api_key=None,
      temperature=0.0,
      max_output_tokens=4096,
    )
    assert result == mock_llm_instance

  @patch("app.services.ml_models.config")
  def test_get_main_llm_model_unsupported_provider(self, mock_config):
    """Testa get_main_llm_model quando o provedor não é suportado."""
    mock_config.env.llm_provider = "unsupported_provider"
    mock_config.env.llm_model = "custom-model"
    mock_config.env.llm_api_key = None
    mock_config.env.llm_temperature = 0.5
    mock_config.env.llm_max_tokens = 1000

    with pytest.raises(AttributeError):
      MLModelsService.get_main_llm_model()

  @patch("app.services.ml_models.config")
  def test_main_llm_model_property(self, mock_config):
    """Testa o acesso à propriedade main_llm_model."""
    mock_config.env.llm_model = "gpt-4o"
    # Como está decorado com @property em um método @staticmethod na classe,
    # verificamos o comportamento em instância e a chamada direta
    instance = MLModelsService()
    assert (
      MLModelsService.main_llm_model()
      if callable(MLModelsService.main_llm_model)
      else (
        instance.main_llm_model()
        if callable(instance.main_llm_model)
        else MLModelsService.main_llm_model.fget()
      )
    ) == "gpt-4o"
