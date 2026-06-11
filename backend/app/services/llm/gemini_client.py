import asyncio
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError, ResourceExhausted
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """Google Gemini Flash client for text generation."""

    def __init__(self, api_key: str):
        if not api_key or api_key == "your_gemini_key_here":
            logger.warning("Gemini API key is missing or default. LLM calls will fail.")
        genai.configure(api_key=api_key)
        # Using gemini-2.5-flash as the actual model identifier
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        """Asynchronously call Gemini API with retry logic for rate limit hits."""
        max_retries = 3
        backoff = 2.0

        # In google-generativeai, system instructions are passed at model initialization
        # or during generate_content as system_instruction.
        def _generate():
            # We can pass system instructions directly if supported, or prepended to the content
            config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            response = self.model.generate_content(
                contents=f"System Prompt:\n{system_prompt}\n\nUser Message:\n{user_message}",
                generation_config=config,
            )
            return response.text

        for attempt in range(max_retries):
            try:
                text = await asyncio.to_thread(_generate)
                return text
            except ResourceExhausted as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "Gemini rate limit exceeded. Retrying...",
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise LLMError(
                        message="Gemini API rate limit exceeded after retries",
                        details={"error": str(e)},
                    )
            except GoogleAPIError as e:
                logger.error("Gemini API error", error=str(e))
                raise LLMError(
                    message="Gemini API generation failed",
                    details={"error": str(e)},
                )
            except Exception as e:
                logger.error("Unexpected error in Gemini client", error=str(e))
                raise LLMError(
                    message="Unexpected error during LLM generation",
                    details={"error": str(e)},
                )
