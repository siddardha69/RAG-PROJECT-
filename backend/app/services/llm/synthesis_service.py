import json
import re
from typing import Dict, List, Tuple, Union, Optional, Any
from uuid import UUID
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.openai_client import OpenAIClient
from app.services.retrieval.vector_retriever import RetrievedChunk

logger = get_logger(__name__)

EXPLANATION_SYSTEM_PROMPT = """
You are an engineering historian with deep expertise in software architecture.
Your role is to explain engineering decisions using only the evidence provided.

You MUST:
- Cite every claim with the artifact ID in brackets: [artifact_id]
- Structure your answer as: What happened → Why it happened → Alternatives considered → Evidence summary
- Be precise and technical
- Acknowledge when evidence is incomplete
- Never invent or assume facts not present in the evidence

You MUST NOT:
- Hallucinate any technical details
- Make recommendations unless specifically asked
- Reference information not in the provided context
"""

RECOMMENDATION_SYSTEM_PROMPT = """
You are a principal engineer evaluating whether a past technical decision should be revisited.

Given the original decision evidence and the question, provide:
1. Original assumptions (what was true when the decision was made)
2. Current risks (what may have changed)
3. Recommendation (keep / revisit / replace)
4. Confidence level (0.0–1.0)

Format your response as JSON:
{
  "original_assumption": "...",
  "current_risk": "...",
  "recommendation": "keep|revisit|replace",
  "recommendation_rationale": "...",
  "confidence": 0.0
}
"""


class SynthesisService:
    """Orchestrates LLM calls to synthesize explanations and recommendations from context chunks."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.gemini_client = GeminiClient(self.settings.gemini_api_key)
        self.openai_client = OpenAIClient(self.settings.openai_api_key)

    def _get_llm_client(self) -> Union[GeminiClient, OpenAIClient]:
        """Determine which LLM provider client to return based on settings."""
        if self.settings.llm_provider.lower() == "gemini":
            return self.gemini_client
        return self.openai_client

    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """
        Build context string from chunks.
        Sorted by created_at ascending (temporal order).
        """
        # Sort chronologically
        sorted_chunks = sorted(chunks, key=lambda x: x.created_at)

        context_parts = []
        for chunk in sorted_chunks:
            hdr = f"[{chunk.artifact_id}] {chunk.artifact_type.upper()} | {chunk.author} | {chunk.created_at.isoformat()} | {chunk.chunk_type}"
            part = f"{hdr}\n---\n{chunk.text}\n---"
            context_parts.append(part)

        return "\n\n".join(context_parts)

    async def explain_decision(
        self,
        question: str,
        chunks: List[RetrievedChunk],
    ) -> Tuple[str, float]:
        """Generate cited answer explaining the engineering decisions."""
        if not chunks:
            return "Not enough evidence found to explain this decision.", 0.0

        context = self._build_context(chunks)
        user_message = f"Question: {question}\n\nEvidence Context:\n{context}"

        client = self._get_llm_client()
        logger.info("Generating decision explanation with LLM", provider=self.settings.llm_provider)
        answer = await client.generate(
            system_prompt=EXPLANATION_SYSTEM_PROMPT,
            user_message=user_message,
        )

        # Confidence score: len(chunks) / 5 capped at 1.0
        confidence = min(len(chunks) / 5.0, 1.0)
        return answer, confidence

    async def generate_recommendation(
        self,
        artifact_id: UUID,
        context: str,
    ) -> Dict[str, Any]:
        """Generate design risk recommendation in JSON format."""
        user_message = f"Artifact ID under review: {artifact_id}\n\nDecision Context:\n{context}"

        client = self._get_llm_client()
        logger.info("Generating risk recommendation with LLM", provider=self.settings.llm_provider)

        raw_response = await client.generate(
            system_prompt=RECOMMENDATION_SYSTEM_PROMPT,
            user_message=user_message,
        )

        # Clean JSON blocks if present
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            # Strip ```json or ``` at beginning
            cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
            # Strip ``` at end
            cleaned = re.sub(r"\n```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            # Validate required keys
            required_keys = ["original_assumption", "current_risk", "recommendation", "confidence"]
            for k in required_keys:
                if k not in parsed:
                    parsed[k] = "N/A" if k != "confidence" else 0.5

            # Ensure recommendation is lowercased keep/revisit/replace
            rec = str(parsed.get("recommendation", "keep")).lower()
            if rec not in ("keep", "revisit", "replace"):
                parsed["recommendation"] = "revisit"
            else:
                parsed["recommendation"] = rec

            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON recommendation from LLM response", error=str(e), response=raw_response)
            return {
                "original_assumption": "Could not extract assumptions due to parsing error.",
                "current_risk": "Could not extract risks due to parsing error.",
                "recommendation": "revisit",
                "recommendation_rationale": f"Parsing failure: {cleaned}",
                "confidence": 0.3,
            }

