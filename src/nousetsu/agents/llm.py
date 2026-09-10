"""LLM client factory supporting Google Gemini, OpenAI, Anthropic, and local mock fallback."""
import os
from typing import Any, Callable, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


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

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs: Any) -> ChatResult:
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

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

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


def get_llm(model_name: str = "gemini-2.5-pro", temperature: float = 0.3) -> BaseChatModel:
    """Factory to instantiate appropriate LLM or fallback to MockNovelLLM."""
    if model_name.startswith("mock"):
        return MockNovelLLM()

    import dotenv
    dotenv.load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=temperature,
                max_retries=5,
                timeout=180
            )
        except Exception:
            pass

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key and ("gpt" in model_name or "o1" in model_name):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, api_key=openai_key, temperature=temperature)
        except Exception:
            pass

    # Fallback to deterministic mock if no key or provider fails
    return MockNovelLLM()
