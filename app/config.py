import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://aether:aether_pass@localhost:5432/aether_db")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    # Azure OpenAI / Foundry settings (read from .env)
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/openai/v1")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    azure_openai_key: str = os.getenv("AZURE_OPENAI_KEY", "")
    # Convenience aliases used elsewhere in the code
    azure_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    azure_api_key: str = os.getenv("AZURE_OPENAI_KEY", "")
    agent_max_iterations: int = 5
    short_term_history: int = 20
    disable_tool_sandbox: bool = os.getenv("DISABLE_TOOL_SANDBOX", "false").lower() in ("1", "true")
    # azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "https://<your-resource>.openai.azure.com")
    # azure_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "grok-4-20-non-reasoning")
    # azure_api_key: str = os.getenv("AZURE_OPENAI_KEY", "")

    class Config:
        env_file = ".env"


settings = Settings()
