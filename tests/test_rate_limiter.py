"""Unit tests for sliding-window rate limiter, token estimation, and 429 backoff."""
from pathlib import Path
import threading
import time
from rich.console import Console
import pytest

from nousetsu.agents.llm import is_rate_limit_error, parse_retry_delay, invoke_with_retry
from nousetsu.batch.runner import BatchRunner
from nousetsu.models.exceptions import BatchStoppedException
from nousetsu.models.metadata import StageStatus
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter, estimate_tokens


def test_estimate_tokens():
    # Empty
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0

    # English text: 10 words
    en_text = "The hero entered the ancient dungeon and found the treasure."
    en_tokens = estimate_tokens(en_text)
    assert 10 <= en_tokens <= 25

    # Japanese text: 15 CJK chars
    jp_text = "少年は魔導の剣を手に取って歩き出した。"
    jp_tokens = estimate_tokens(jp_text)
    assert 15 <= jp_tokens <= 35

    # Chinese text
    zh_text = "在这个古老的大陆上，修行者逆天改命。"
    zh_tokens = estimate_tokens(zh_text)
    assert 15 <= zh_tokens <= 40

    # Korean text
    ko_text = "주인공은 던전으로 향했다."
    ko_tokens = estimate_tokens(ko_text)
    assert 8 <= ko_tokens <= 25


def test_sliding_window_rate_limiter_rpm():
    # 3 RPM with 0.4s window
    limiter = SlidingWindowRateLimiter(max_tpm=100000, max_rpm=3, window_seconds=0.4)

    # First 3 requests should be immediate
    w1 = limiter.acquire(estimated_tokens=10)
    w2 = limiter.acquire(estimated_tokens=10)
    w3 = limiter.acquire(estimated_tokens=10)
    assert w1 == 0.0
    assert w2 == 0.0
    assert w3 == 0.0

    # 4th request must wait for the oldest to expire (~0.4s)
    start_t = time.time()
    w4 = limiter.acquire(estimated_tokens=10)
    elapsed = time.time() - start_t

    assert elapsed >= 0.35
    assert w4 > 0.3


def test_sliding_window_rate_limiter_tpm():
    # 1000 TPM with 0.4s window
    limiter = SlidingWindowRateLimiter(max_tpm=1000, max_rpm=100, window_seconds=0.4)

    # 600 tokens -> immediate
    assert limiter.acquire(estimated_tokens=600) == 0.0
    # 300 tokens -> immediate (total 900)
    assert limiter.acquire(estimated_tokens=300) == 0.0

    # Next 300 tokens would exceed 1000 TPM (900 + 300 = 1200 > 1000)
    start_t = time.time()
    w3 = limiter.acquire(estimated_tokens=300)
    elapsed = time.time() - start_t

    assert elapsed >= 0.35
    assert w3 > 0.3


def test_rate_limiter_interruptible():
    # Force a long wait with a small limit
    limiter = SlidingWindowRateLimiter(max_tpm=100, max_rpm=1, window_seconds=10.0)
    limiter.acquire(estimated_tokens=80)

    stop_event = threading.Event()
    # Schedule stop_event in 0.1s
    timer = threading.Timer(0.1, stop_event.set)
    timer.start()

    with pytest.raises(BatchStoppedException):
        limiter.acquire(estimated_tokens=80, stop_event=stop_event)

    timer.cancel()


def test_parse_retry_delay():
    class CustomErr(Exception):
        pass

    e1 = CustomErr("Resource has been exhausted. Please retry in 42.5s.")
    assert parse_retry_delay(e1) == 42.5

    e2 = CustomErr("Rate limit reached. Please wait 15 seconds before retrying.")
    assert parse_retry_delay(e2) == 15.0

    e3 = CustomErr("Quota reset in 60s")
    assert parse_retry_delay(e3) == 60.0

    e4 = CustomErr("Internal server error 500")
    assert parse_retry_delay(e4) is None

    # retry_after attribute
    e5 = CustomErr("Too Many Requests")
    e5.retry_after = "25.0"
    assert parse_retry_delay(e5) == 25.0


def test_is_rate_limit_error():
    assert is_rate_limit_error(Exception("429 Too Many Requests")) is True
    assert is_rate_limit_error(Exception("google.api_core.exceptions.ResourceExhausted: 429")) is True
    assert is_rate_limit_error(Exception("Rate limit exceeded")) is True
    assert is_rate_limit_error(Exception("Quota exceeded for metric")) is True
    assert is_rate_limit_error(Exception("500 Internal Server Error")) is False


def test_invoke_with_retry_rate_limited():
    limiter = SlidingWindowRateLimiter(max_tpm=16000, max_rpm=60)
    call_count = 0

    def dummy_func(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    res = invoke_with_retry(
        dummy_func,
        21,
        rate_limiter=limiter,
        estimated_tokens=500
    )

    assert res == 42
    assert call_count == 1
    rpm, tpm = limiter.get_current_usage()
    assert rpm == 1
    assert tpm == 500


def test_batch_runner_with_16k_rate_limiter(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Rate Limit Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "ch_01.txt").write_text("第一章：少年の冒険。\n世界を救う旅に出る。", encoding="utf-8")

    console = Console(record=True)
    # Runner configured with 16k TPM and 60 RPM
    runner = BatchRunner(
        repo,
        model_name="mock-model",
        max_tpm=16000,
        max_rpm=60,
        console=console
    )

    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(results) == 1
    assert results[0].checkpoint.status == StageStatus.COMPLETED
    assert (output_dir / "ch_01.md").exists()

    # Verify rate limiter tracked the requests
    rpm, tpm = runner.rate_limiter.get_current_usage()
    assert rpm > 0
    assert tpm > 0
