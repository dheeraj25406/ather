import logging
import httpx
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaLLM:
    def __init__(self):
        self.base_url = settings.ollama_url
        # Use model available in Ollama container; pull llama2 in Docker Compose setup
        self.model = "llama3"

    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate text using Ollama LLM."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": max_tokens,
                "top_p": 0.9,
            }
        }
        
        try:
            logger.info(f"LLM request: model={self.model}, prompt_len={len(prompt)}, max_tokens={max_tokens}")
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                result = data.get("response", "").strip()
                duration = data.get("total_duration", 0) / 1e9  # nanoseconds to seconds
                logger.info(f"LLM response: {len(result)} chars, duration={duration:.1f}s")
                return result
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"LLM Error: {str(e)}"


class AzureOpenAILLM:
    def __init__(self):
        # endpoint should include the /openai/v1 path if you used that in .env
        self.base_url = settings.azure_openai_endpoint.rstrip("/")
        self.deployment = settings.azure_openai_deployment
        self.api_key = settings.azure_openai_key
        # create the OpenAI client (the library will use the endpoint + api_key)
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Uses the OpenAI client to call Azure OpenAI (chat completion via deployment).
        """
        try:
            # create a chat completion using the deployment name as the model param
            completion = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens
            )
            # Access the text returned by the model:
            # depending on library version the structure may be .choices[0].message or dict-like
            choice = completion.choices[0]
            message = getattr(choice, "message", None) or choice.get("message", {})
            # final content may be under .content or ['content']
            content = getattr(message, "content", None) or message.get("content", "")
            return content.strip()
        except Exception as e:
            logger.error("AzureOpenAI LLM error: %s", e)
            return f"LLM Error: {e}"