import asyncio
from openai import AsyncOpenAI, RateLimitError, OpenAIError
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """OpenAI GPT-4o fallback client."""

    def __init__(self, api_key: str):
        if not api_key or api_key == "sk-your_openai_key_here":
            logger.warning("OpenAI API key is missing or default. Fallback will fail.")
        self.client = AsyncOpenAI(api_key=api_key or "mock-openai-key-value")

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        """Call openai chat completions with exponential backoff on RateLimitError."""
        max_retries = 3
        backoff = 2.0

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise LLMError("OpenAI returned an empty response")
                return content
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "OpenAI rate limit hit. Retrying...",
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise LLMError(
                        message="OpenAI rate limit exceeded after retries",
                        details={"error": str(e)},
                    )
            except OpenAIError as e:
                logger.error("OpenAI API error", error=str(e))
                raise LLMError(
                    message="OpenAI API generation failed",
                    details={"error": str(e)},
                )
            except Exception as e:
                logger.error("Unexpected error in OpenAI client", error=str(e))
                raise LLMError(
                    message="Unexpected error during LLM generation",
                    details={"error": str(e)},
                )
