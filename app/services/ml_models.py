from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.configs import config


class MLModelsService:

  @staticmethod
  def get_main_llm_model() -> ChatGoogleGenerativeAI | ChatOpenAI  | ChatOllama: 
    model_name = config.env.llm_model
    provider = config.env.llm_provider
    api_key = config.env.llm_api_key
    temp = config.env.llm_temperature
    max_tokens = config.env.llm_max_tokens

    method_name = f"_load_llm_model_{provider}"
    load = getattr(MLModelsService, method_name)

    llm = load(model_name, **{"api_key": api_key, "temperature": temp, "max_output_tokens": max_tokens})
    return llm

  @staticmethod
  @property
  def main_llm_model() -> str: 
    return config.env.llm_model


  @staticmethod
  def _load_llm_model_google(model: str, **kwargs): 
    return ChatGoogleGenerativeAI(model=model, **kwargs)

  @staticmethod
  def _load_llm_model_openai(model: str, **kwargs): 
    max_tokens = kwargs.pop("max_output_tokens", None)
    if max_tokens:
      kwargs["max_completion_tokens"] = max_tokens

    return ChatOpenAI(model=model, **kwargs)

  @staticmethod
  def _load_llm_model_ollama(model: str, **kwargs): 
    max_tokens = kwargs.pop("max_output_tokens", None)
    if max_tokens:
      kwargs["num_predict"] = max_tokens

    kwargs.pop("api_key", None)

    return ChatOllama(model=model, **kwargs)
