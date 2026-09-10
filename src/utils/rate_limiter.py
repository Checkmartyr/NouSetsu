"""Sliding-window token and request rate limiter for API quotas (e.g. 16K TPM / 60 RPM)."""
from collections import deque
import re
import threading
import time
from typing import Callable, Optional, Tuple
from src.models.exceptions import BatchStoppedException


def estimate_tokens(text: str) -> int:
    """
    Estimate LLM token count for mixed novel text (CJK + Latin).
    Runs offline in <1ms without requiring external heavy tokenizer libraries.

    Heuristics:
    - CJK characters (Hiragana, Katakana, Hanzi/Kanji, Hangul): ~1.7 tokens per character.
    - Latin words / symbols: ~1.3 tokens per word (or ~4 chars per token).
    """
    if not text:
        return 0

    # Count CJK ideographs, Kana, and Hangul
    cjk_chars = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uac00-\ud7af\u1100-\u11ff]", text))

    # Remove CJK chars to count remaining Latin/alphanumeric text
    non_cjk_text = re.sub(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uac00-\ud7af\u1100-\u11ff]", " ", text)
    latin_words = len(re.findall(r"\b\w+\b", non_cjk_text))
    remaining_symbols = len(re.findall(r"[^\w\s]", non_cjk_text))

    cjk_tokens = int(cjk_chars * 1.7)
    latin_tokens = int(latin_words * 1.3) + int(remaining_symbols * 0.5)

    return max(1, cjk_tokens + latin_tokens)


class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window rate limiter enforcing Requests Per Minute (RPM)
    and Tokens Per Minute (TPM). Supports interruptible sleep via stop_event.
    """

    def __init__(
        self,
        max_tpm: int = 16000,
        max_rpm: int = 60,
        window_seconds: float = 60.0
    ):
        self.max_tpm = max_tpm
        self.max_rpm = max_rpm
        self.window_seconds = window_seconds

        self.request_timestamps: deque[float] = deque()
        self.token_records: deque[Tuple[float, int]] = deque()  # (timestamp, tokens)
        self._lock = threading.Lock()

    def _purge_expired(self, now: float) -> None:
        """Remove records older than window_seconds."""
        cutoff = now - self.window_seconds
        while self.request_timestamps and self.request_timestamps[0] <= cutoff:
            self.request_timestamps.popleft()
        while self.token_records and self.token_records[0][0] <= cutoff:
            self.token_records.popleft()

    def get_current_usage(self) -> Tuple[int, int]:
        """Return (current_rpm, current_tpm) in the active rolling window."""
        with self._lock:
            now = time.time()
            self._purge_expired(now)
            rpm = len(self.request_timestamps)
            tpm = sum(tok for _, tok in self.token_records)
            return rpm, tpm

    def acquire(
        self,
        estimated_tokens: int = 1000,
        stop_event: Optional[threading.Event] = None,
        notify_callback: Optional[Callable[[str], None]] = None
    ) -> float:
        """
        Wait until there is sufficient RPM and TPM capacity in the sliding window.
        Returns the total wait time in seconds.
        """
        total_waited = 0.0

        while True:
            if stop_event and stop_event.is_set():
                raise BatchStoppedException("Operation cancelled by user during rate limit wait.")

            with self._lock:
                now = time.time()
                self._purge_expired(now)

                current_rpm = len(self.request_timestamps)
                current_tpm = sum(tok for _, tok in self.token_records)

                # Check RPM limit
                rpm_wait = 0.0
                if current_rpm >= self.max_rpm and self.request_timestamps:
                    oldest_req = self.request_timestamps[0]
                    rpm_wait = max(0.0, (oldest_req + self.window_seconds) - now + 0.1)

                # Check TPM limit
                tpm_wait = 0.0
                if current_tpm + estimated_tokens > self.max_tpm and self.token_records:
                    # Calculate how long until enough tokens expire
                    tokens_needed_to_free = (current_tpm + estimated_tokens) - self.max_tpm
                    freed = 0
                    for ts, tok in self.token_records:
                        freed += tok
                        if freed >= tokens_needed_to_free:
                            tpm_wait = max(0.0, (ts + self.window_seconds) - now + 0.1)
                            break

                needed_wait = max(rpm_wait, tpm_wait)

                if needed_wait <= 0.0:
                    # Within capacity: reserve tokens and record request
                    self.request_timestamps.append(now)
                    self.token_records.append((now, estimated_tokens))
                    return total_waited

            # Need to pause for capacity
            if notify_callback:
                reason = []
                if tpm_wait > 0:
                    reason.append(f"TPM: {current_tpm + estimated_tokens}/{self.max_tpm}")
                if rpm_wait > 0:
                    reason.append(f"RPM: {current_rpm + 1}/{self.max_rpm}")
                reason_str = ", ".join(reason)
                msg = f"⏳ Rate Limit Guard (16K TPM / 60 RPM): {reason_str}. Throttling for {needed_wait:.1f}s to avoid 429..."
                try:
                    notify_callback(msg)
                except Exception:
                    pass

            # Sleep in 200ms intervals to remain responsive to stop_event
            sleep_chunk = min(needed_wait, 0.25)
            time.sleep(sleep_chunk)
            total_waited += sleep_chunk

    def record_usage(self, actual_tokens: int) -> None:
        """Optionally adjust the most recent token record with actual usage."""
        with self._lock:
            if self.token_records:
                ts, _ = self.token_records[-1]
                self.token_records[-1] = (ts, actual_tokens)

    def reset(self) -> None:
        """Clear sliding window records."""
        with self._lock:
            self.request_timestamps.clear()
            self.token_records.clear()
