"""Gemini Interactions API client and LangChain BaseChatModel adapter.

Supports Google's official Gemini Interactions API (/v1beta/interactions),
extracting fine-grained token usage (prompt, completion, thought/reasoning, cached, total).
"""
from dataclasses import dataclass
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from nousetsu.models.metadata import TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class InteractionResult:
    """Standardized response from Gemini Interactions API."""
    id: str
    model: str
    output_text: str
    usage: TokenUsage
    raw_response: Any = None


class GeminiInteractionsClient:
    """Client for Google Gemini Interactions API with google.genai SDK and REST fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self._genai_client = None

        if self.api_key:
            try:
                import google.genai
                self._genai_client = google.genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.debug(f"Failed to initialize google.genai.Client: {e}")

    def create(
        self,
        model: str = "gemini-3.1-flash-lite",
        input_data: Union[str, List[Dict[str, Any]]] = "",
        system_instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        timeout: float = 180.0
    ) -> InteractionResult:
        """
        Create a new interaction via google.genai client or direct REST endpoint.
        """
        # Try google.genai SDK client first
        if self._genai_client is not None and hasattr(self._genai_client, "interactions"):
            try:
                kwargs: Dict[str, Any] = {
                    "model": model,
                    "input": input_data,
                }
                if system_instruction:
                    kwargs["system_instruction"] = system_instruction
                if generation_config:
                    kwargs["generation_config"] = generation_config

                interaction = self._genai_client.interactions.create(**kwargs)
                return self._parse_sdk_interaction(interaction, model)
            except Exception as sdk_err:
                logger.debug(f"SDK interactions.create failed ({sdk_err}); attempting REST fallback...")

        # Fallback: direct HTTP POST to /v1beta/interactions
        return self._rest_create_interaction(
            model=model,
            input_data=input_data,
            system_instruction=system_instruction,
            generation_config=generation_config,
            timeout=timeout
        )

    def _parse_sdk_interaction(self, interaction: Any, model: str) -> InteractionResult:
        """Parse interaction object returned by google.genai SDK."""
        inter_id = getattr(interaction, "id", "") or ""
        inter_model = getattr(interaction, "model", model) or model

        # Extract text: SDK provides .output_text directly via _add_output_properties_if_interaction
        output_text = getattr(interaction, "output_text", None)
        if not output_text:
            output_text = self._extract_text_from_steps(getattr(interaction, "steps", None))

        # Extract token usage
        usage_obj = getattr(interaction, "usage", None)
        usage = self._parse_usage_payload(usage_obj)

        return InteractionResult(
            id=inter_id,
            model=inter_model,
            output_text=output_text or "",
            usage=usage,
            raw_response=interaction
        )

    def _rest_create_interaction(
        self,
        model: str,
        input_data: Union[str, List[Dict[str, Any]]],
        system_instruction: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        timeout: float = 180.0
    ) -> InteractionResult:
        """Direct REST POST to https://generativelanguage.googleapis.com/v1beta/interactions."""
        import httpx

        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        payload: Dict[str, Any] = {
            "model": model,
            "input": input_data
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction
        if generation_config:
            payload["generation_config"] = generation_config

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        inter_id = data.get("id", "")
        inter_model = data.get("model", model)
        steps = data.get("steps", [])
        output_text = self._extract_text_from_steps(steps)
        usage = self._parse_usage_payload(data.get("usage"))

        return InteractionResult(
            id=inter_id,
            model=inter_model,
            output_text=output_text or "",
            usage=usage,
            raw_response=data
        )

    def _extract_text_from_steps(self, steps: Any) -> str:
        """Extract output text from interaction steps."""
        if not steps:
            return ""
        text_parts: List[str] = []
        for step in steps:
            stype = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
            if stype == "model_output":
                content = getattr(step, "content", None) or (step.get("content") if isinstance(step, dict) else None)
                if isinstance(content, list):
                    for item in content:
                        itype = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                        if itype == "text":
                            txt = getattr(item, "text", None) or (item.get("text") if isinstance(item, dict) else None)
                            if txt:
                                text_parts.append(txt)
                        elif isinstance(item, str):
                            text_parts.append(item)
        return "\n".join(text_parts).strip()

    def _parse_usage_payload(self, usage_obj: Any) -> TokenUsage:
        """Normalize usage dict/object from Interactions API into TokenUsage."""
        if not usage_obj:
            return TokenUsage()

        if isinstance(usage_obj, dict):
            inp = usage_obj.get("total_input_tokens") or usage_obj.get("input_tokens") or 0
            out = usage_obj.get("total_output_tokens") or usage_obj.get("output_tokens") or 0
            tht = usage_obj.get("total_thought_tokens") or usage_obj.get("thought_tokens") or 0
            cch = usage_obj.get("total_cached_tokens") or usage_obj.get("cached_tokens") or 0
            tot = usage_obj.get("total_tokens") or (inp + out + tht)
            return TokenUsage(
                input_tokens=int(inp),
                output_tokens=int(out),
                thought_tokens=int(tht),
                cached_tokens=int(cch),
                total_tokens=int(tot)
            )

        # Object attributes
        inp = getattr(usage_obj, "total_input_tokens", 0) or 0
        out = getattr(usage_obj, "total_output_tokens", 0) or 0
        tht = getattr(usage_obj, "total_thought_tokens", 0) or 0
        cch = getattr(usage_obj, "total_cached_tokens", 0) or 0
        tot = getattr(usage_obj, "total_tokens", 0) or (inp + out + tht)
        return TokenUsage(
            input_tokens=int(inp),
            output_tokens=int(out),
            thought_tokens=int(tht),
            cached_tokens=int(cch),
            total_tokens=int(tot)
        )


class GeminiInteractionsChatModel(BaseChatModel):
    """LangChain BaseChatModel adapter powered by Google Gemini Interactions API."""

    model_name: str = "gemini-3.1-flash-lite"
    temperature: float = 0.3
    api_key: Optional[str] = None
    timeout: float = 180.0
    client: Optional[GeminiInteractionsClient] = None

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if self.client is None:
            self.client = GeminiInteractionsClient(api_key=self.api_key)

    @property
    def _llm_type(self) -> str:
        return "gemini_interactions"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        sys_instructions: List[str] = []
        user_inputs: List[Dict[str, Any]] = []
        last_user_text: List[str] = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                sys_instructions.append(str(msg.content))
            elif isinstance(msg, HumanMessage):
                user_inputs.append({"type": "user_input", "content": [{"type": "text", "text": str(msg.content)}]})
                last_user_text.append(str(msg.content))
            elif isinstance(msg, AIMessage):
                user_inputs.append({"type": "model_output", "content": [{"type": "text", "text": str(msg.content)}]})
            else:
                user_inputs.append({"type": "user_input", "content": [{"type": "text", "text": str(msg.content)}]})
                last_user_text.append(str(msg.content))

        system_instruction = "\n\n".join(sys_instructions) if sys_instructions else None

        # For simple single human prompt, pass input as string or steps
        if len(user_inputs) == 1 and user_inputs[0].get("type") == "user_input":
            input_data: Union[str, List[Dict[str, Any]]] = last_user_text[-1] if last_user_text else ""
        else:
            input_data = user_inputs

        gen_config: Dict[str, Any] = {}
        if stop:
            gen_config["stop_sequences"] = stop

        # If hybrid reasoning model, set moderate thinking level
        if any(h in self.model_name for h in ["2.5-pro", "2.5-flash", "3.", "reasoning"]):
            gen_config["thinking_level"] = "low"

        assert self.client is not None, "GeminiInteractionsClient is not initialized"
        result = self.client.create(
            model=self.model_name,
            input_data=input_data,
            system_instruction=system_instruction,
            generation_config=gen_config if gen_config else None,
            timeout=self.timeout
        )

        usage_dict = {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
            "thought_tokens": result.usage.thought_tokens,
            "cached_tokens": result.usage.cached_tokens
        }

        resp_metadata = {
            "interaction_id": result.id,
            "model": result.model,
            "usage": usage_dict
        }

        ai_message = AIMessage(
            content=result.output_text,
            usage_metadata=usage_dict,
            response_metadata=resp_metadata
        )

        return ChatResult(generations=[ChatGeneration(message=ai_message)])
