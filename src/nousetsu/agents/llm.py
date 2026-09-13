"""LLM client factory supporting Google Gemini, OpenAI, Anthropic, and local mock fallback."""
import os
from typing import Any, Callable, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field
from nousetsu.models.metadata import TokenUsage


def extract_usage_from_message(msg: Any) -> TokenUsage:
    """Extract fine-grained TokenUsage from an AIMessage, response object, or dict."""
    if not msg:
        return TokenUsage()

    # Case 1: Standard LangChain usage_metadata
    if hasattr(msg, "usage_metadata") and isinstance(msg.usage_metadata, dict) and msg.usage_metadata:
        um = msg.usage_metadata
        return TokenUsage(
            input_tokens=int(um.get("input_tokens", 0) or 0),
            output_tokens=int(um.get("output_tokens", 0) or 0),
            total_tokens=int(um.get("total_tokens", 0) or 0),
            thought_tokens=int(um.get("thought_tokens", 0) or 0),
            cached_tokens=int(um.get("cached_tokens", 0) or 0),
        )

    # Case 2: Response metadata from Gemini Interactions or LangChain
    if hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict) and msg.response_metadata:
        rm = msg.response_metadata
        if "usage" in rm:
            u = rm["usage"]
            if isinstance(u, TokenUsage):
                return u
            if hasattr(u, "total_tokens"):
                return TokenUsage(
                    input_tokens=int(getattr(u, "total_input_tokens", 0) or 0),
                    output_tokens=int(getattr(u, "total_output_tokens", 0) or 0),
                    thought_tokens=int(getattr(u, "total_thought_tokens", 0) or 0),
                    cached_tokens=int(getattr(u, "total_cached_tokens", 0) or 0),
                    total_tokens=int(getattr(u, "total_tokens", 0) or 0),
                )
            if isinstance(u, dict):
                return TokenUsage(
                    input_tokens=int(u.get("total_input_tokens") or u.get("input_tokens", 0) or 0),
                    output_tokens=int(u.get("total_output_tokens") or u.get("output_tokens", 0) or 0),
                    thought_tokens=int(u.get("total_thought_tokens") or u.get("thought_tokens", 0) or 0),
                    cached_tokens=int(u.get("total_cached_tokens") or u.get("cached_tokens", 0) or 0),
                    total_tokens=int(u.get("total_tokens", 0) or 0),
                )
        if "token_usage" in rm and isinstance(rm["token_usage"], dict):
            tu = rm["token_usage"]
            return TokenUsage(
                input_tokens=int(tu.get("prompt_tokens", 0) or 0),
                output_tokens=int(tu.get("completion_tokens", 0) or 0),
                total_tokens=int(tu.get("total_tokens", 0) or 0),
            )

    # Case 3: Raw dict with token usage keys
    if isinstance(msg, dict):
        if "usage" in msg:
            return extract_usage_from_message(msg["usage"])
        return TokenUsage(
            input_tokens=int(msg.get("input_tokens") or msg.get("prompt_tokens", 0) or 0),
            output_tokens=int(msg.get("output_tokens") or msg.get("completion_tokens", 0) or 0),
            thought_tokens=int(msg.get("thought_tokens", 0) or 0),
            cached_tokens=int(msg.get("cached_tokens", 0) or 0),
            total_tokens=int(msg.get("total_tokens", 0) or 0),
        )

    return TokenUsage()


def extract_text_from_message(content: Any) -> str:
    """Extract plain text from LLM response content, discarding thinking/reasoning blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                # Only keep text type parts, discard thinking/reasoning blocks
                if part.get("type") == "text" and "text" in part:
                    text_parts.append(part["text"])
                elif part.get("type") != "thinking" and "text" in part:
                    text_parts.append(part["text"])
        if text_parts:
            return "\n".join(text_parts).strip()
    return str(content).strip()


class MockNovelLLM(BaseChatModel):
    """Deterministic mock LLM for testing without external API keys."""

    model_name: str = "mock-novel-llm"
    temperature: float = 1.0
    responses: list[str] = Field(default_factory=list)

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs: Any) -> ChatResult:
        if self.responses:
            content = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        else:
            last_msg = messages[-1].content if messages else ""
            first_msg = messages[0].content if messages else ""

            # Check which prompt was passed based on content clues
            if "new_characters" in str(first_msg) or "Extracting" in str(last_msg):
                content = '{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}'
            elif "fidelity_score" in str(first_msg):
                content = '{"fidelity_score": 9.5, "style_score": 9.2, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Good flow, prose is faithful."}'
            elif "synopsis" in str(first_msg):
                content = '{"chapter_num": 1, "title": "Chapter", "synopsis": "The journey begins.", "key_events": ["Protagonist departs"], "character_state_changes": []}'
            elif "literary prose stylist" in str(first_msg) or "POLISHING RULES" in str(first_msg) or "elite novelist" in str(first_msg):
                content = "# Polished Chapter\n\nChapter 1: The signal of departure. The boy stepped forward with quiet determination."
            elif "CRITICAL TRANSLATION DIRECTIVES" in str(first_msg) or "literary translator" in str(first_msg):
                content = "# Translated Chapter\n\nChapter 1: The signal of departure. The boy stepped forward into the unknown."
            else:
                content = "# Translated Chapter\n\nChapter 1: The signal of departure. The boy stepped forward."

        in_tokens = max(1, sum(len(str(m.content)) for m in messages) // 4)
        out_tokens = max(1, len(content) // 4)
        total_tokens = in_tokens + out_tokens
        usage_dict = {
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": total_tokens,
            "thought_tokens": 0,
            "cached_tokens": 0,
        }
        resp_meta = {
            "model": self.model_name,
            "usage": {
                "total_input_tokens": in_tokens,
                "total_output_tokens": out_tokens,
                "total_thought_tokens": 0,
                "total_cached_tokens": 0,
                "total_tokens": total_tokens,
            }
        }
        ai_msg = AIMessage(content=content, usage_metadata=usage_dict, response_metadata=resp_meta)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    @property
    def _llm_type(self) -> str:
        return "mock_novel_llm"


import re


def is_rate_limit_error(err: Exception) -> bool:
    """Check if exception is an HTTP 429 or quota limit exhaustion."""
    msg = str(err).lower()
    return any(ind in msg for ind in ["429", "resourceexhausted", "resource_exhausted", "rate limit", "rate_limit", "quota exceeded", "quota"])


def parse_retry_delay(err: Exception) -> Optional[float]:
    """Parse retry delay in seconds from error message or exception attribute."""
    if hasattr(err, "retry_after") and getattr(err, "retry_after"):
        try:
            return float(getattr(err, "retry_after"))
        except (ValueError, TypeError):
            pass

    msg = str(err)
    match = re.search(r"(?:retry\s+(?:in|after)|reset\s+in|wait)\s*([\d\.]+)\s*(?:s|sec|seconds)?", msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            pass
    return None


def is_transient_error(err: Exception) -> bool:
    """Check if exception is an upstream transient server or rate-limit error."""
    msg = str(err).lower()
    transient_indicators = [
        "500", "503", "502", "504", "internal error", "unavailable",
        "resourceexhausted", "resource_exhausted", "rate limit", "rate_limit",
        "quota", "429", "timeout", "timed out", "connection reset"
    ]
    return any(ind in msg for ind in transient_indicators)


def invoke_with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 6,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    notify_callback: Optional[Callable[[str], None]] = None,
    rate_limiter: Optional[Any] = None,
    estimated_tokens: int = 1000,
    stop_event: Optional[Any] = None,
    **kwargs: Any
) -> Any:
    """
    Execute an LLM call with proactive rate limiting, smart 429 quota backoff,
    and exponential backoff on transient errors.
    """
    import random
    import time
    from nousetsu.models.exceptions import BatchStoppedException

    delay = initial_delay
    last_exc = None

    for attempt in range(1, max_retries + 1):
        if stop_event and stop_event.is_set():
            raise BatchStoppedException("LLM invocation cancelled by user request.")

        # Proactive rate limiting: wait for capacity in sliding window
        if rate_limiter:
            rate_limiter.acquire(
                estimated_tokens=estimated_tokens,
                stop_event=stop_event,
                notify_callback=notify_callback
            )

        try:
            return fn(*args, **kwargs)
        except Exception as err:
            last_exc = err
            if attempt >= max_retries or not is_transient_error(err):
                raise

            # Check if this is a rate-limit / quota error
            if is_rate_limit_error(err):
                parsed_wait = parse_retry_delay(err)
                if parsed_wait and parsed_wait > 0:
                    wait_time = parsed_wait + 1.0  # Add 1s safety buffer
                else:
                    # If 429 without explicit delay, wait for 1-minute window to roll over
                    quota_waits = [25.0, 45.0, 65.0, 65.0, 65.0, 65.0]
                    wait_time = quota_waits[min(attempt - 1, len(quota_waits) - 1)] * random.uniform(0.95, 1.05)

                if notify_callback:
                    try:
                        notify_callback(f"⚠️ Rate Limit (16K TPM / 60 RPM): 429 quota hit. Waiting {wait_time:.1f}s for quota reset (Attempt {attempt}/{max_retries})...")
                    except Exception:
                        pass
            else:
                jitter = random.uniform(0.8, 1.2)
                wait_time = delay * jitter
                if notify_callback:
                    try:
                        notify_callback(f"Server busy ({type(err).__name__}). Retrying in {wait_time:.1f}s (Attempt {attempt}/{max_retries})...")
                    except Exception:
                        pass
                delay *= backoff_factor

            # Interruptible sleep in 250ms chunks
            end_time = time.time() + wait_time
            while time.time() < end_time:
                if stop_event and stop_event.is_set():
                    raise BatchStoppedException("LLM invocation cancelled by user request during backoff.")
                time.sleep(min(0.25, max(0.0, end_time - time.time())))

    if last_exc:
        raise last_exc


class FallbackChatModel(BaseChatModel):
    """ChatModel adapter that executes primary model and falls back to secondary model upon failure/quota exhaustion."""

    primary: BaseChatModel
    fallback: BaseChatModel
    primary_model_name: str = ""
    fallback_model_name: str = ""
    last_model_used: str = ""
    on_fallback: Optional[Callable[[str, Exception], None]] = None

    def __init__(
        self,
        primary: BaseChatModel,
        fallback: BaseChatModel,
        primary_model_name: str = "",
        fallback_model_name: str = "",
        on_fallback: Optional[Callable[[str, Exception], None]] = None,
        **kwargs: Any
    ):
        p_name = primary_model_name or getattr(primary, "model_name", "primary")
        f_name = fallback_model_name or getattr(fallback, "model_name", "fallback")
        super().__init__(
            primary=primary,
            fallback=fallback,
            primary_model_name=p_name,
            fallback_model_name=f_name,
            last_model_used=p_name,
            on_fallback=on_fallback,
            **kwargs
        )

    @property
    def _llm_type(self) -> str:
        return f"fallback({self.primary_model_name}->{self.fallback_model_name})"

    @property
    def model_name(self) -> str:
        return self.last_model_used or self.primary_model_name

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        import logging
        logger = logging.getLogger(__name__)

        try:
            if hasattr(self.primary, "_generate"):
                res = self.primary._generate(messages, stop=stop, **kwargs)
            else:
                ai_msg = self.primary.invoke(messages)
                res = ChatResult(generations=[ChatGeneration(message=ai_msg)])
            self.last_model_used = self.primary_model_name
            return res
        except Exception as err:
            from nousetsu.models.exceptions import BatchStoppedException
            if isinstance(err, BatchStoppedException):
                raise
            logger.warning(
                f"⚠️ Primary model '{self.primary_model_name}' failed ({type(err).__name__}: {err}). "
                f"Falling back to model '{self.fallback_model_name}'."
            )
            if self.on_fallback:
                try:
                    self.on_fallback(self.fallback_model_name, err)
                except Exception:
                    pass
            if hasattr(self.fallback, "_generate"):
                res = self.fallback._generate(messages, stop=stop, **kwargs)
            else:
                ai_msg = self.fallback.invoke(messages)
                res = ChatResult(generations=[ChatGeneration(message=ai_msg)])
            self.last_model_used = self.fallback_model_name
            return res


def _resolve_temperature(temp: Optional[float] = None) -> float:
    if temp is not None:
        return float(temp)
    env_temp = os.environ.get("NOVEL_TEMPERATURE")
    if env_temp:
        try:
            return float(env_temp)
        except (ValueError, TypeError):
            pass
    return 1.0


def _create_single_llm(
    model_name: str = "gemini-3.1-flash-lite",
    temperature: Optional[float] = None,
    use_interactions: Optional[bool] = None
) -> BaseChatModel:
    """Instantiate a single LLM instance."""
    resolved_temp = _resolve_temperature(temperature)
    if model_name.startswith("mock"):
        return MockNovelLLM(model_name=model_name, temperature=resolved_temp)

    import dotenv
    dotenv.load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if api_key:
        env_interactions = os.environ.get("NOVEL_USE_INTERACTIONS", "1").lower() not in ["0", "false", "no"]
        should_use_interactions = env_interactions if use_interactions is None else use_interactions

        # Default to Gemini Interactions API for Gemini/Gemma models
        if should_use_interactions and ("gemini" in model_name or "gemma" in model_name):
            try:
                from nousetsu.agents.interactions import GeminiInteractionsChatModel
                return GeminiInteractionsChatModel(
                    model_name=model_name,
                    temperature=resolved_temp,
                    api_key=api_key
                )
            except Exception:
                pass

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=resolved_temp,
                max_retries=5,
                timeout=180
            )
        except Exception:
            pass

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and ("gpt" in model_name or "o1" in model_name):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, api_key=openai_key, temperature=resolved_temp)
        except Exception:
            pass

    # Fallback to deterministic mock if no key or provider fails
    return MockNovelLLM(model_name=model_name, temperature=resolved_temp)


def get_llm(
    model_name: str = "gemini-3.1-flash-lite",
    temperature: Optional[float] = None,
    use_interactions: Optional[bool] = None,
    fallback_model: Optional[str] = None,
    on_fallback: Optional[Callable[[str, Exception], None]] = None
) -> BaseChatModel:
    """Factory to instantiate appropriate LLM, optionally wrapped with automatic fallback support."""
    resolved_temp = _resolve_temperature(temperature)
    primary_llm = _create_single_llm(
        model_name=model_name,
        temperature=resolved_temp,
        use_interactions=use_interactions
    )

    clean_fallback = (fallback_model or "").strip()
    if clean_fallback and clean_fallback != model_name:
        fallback_llm = _create_single_llm(
            model_name=clean_fallback,
            temperature=resolved_temp,
            use_interactions=use_interactions
        )
        return FallbackChatModel(
            primary=primary_llm,
            fallback=fallback_llm,
            primary_model_name=model_name,
            fallback_model_name=clean_fallback,
            on_fallback=on_fallback
        )

    return primary_llm

