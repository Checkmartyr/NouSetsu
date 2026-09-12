"""Unit tests for token metrics computation and aggregation."""
from nousetsu.analysis.token_metrics import compute_token_summary
from nousetsu.models.metadata import (
    ChapterMetadata,
    CheckpointData,
    PipelineStage,
    StageStatus,
    StepTokenUsage,
    TokenUsage,
    TranslationStats,
)


def test_compute_token_summary_empty():
    summary = compute_token_summary({})
    assert summary.total_chapters == 0
    assert summary.total_tokens == 0
    assert summary.stage_metrics == []
    assert summary.model_metrics == []
    assert summary.chapter_rankings == []
    assert summary.avg_tokens_per_chapter == 0.0
    assert summary.avg_duration_per_chapter == 0.0


def test_compute_token_summary_legacy_fallback():
    # Test chapter with total_tokens=0 but prompt & completion tokens recorded
    ch1 = ChapterMetadata(
        chapter_id="ch_001",
        chapter_num=1,
        source_file="raw_chapters/001.txt",
        source_sha256="abc123",
        output_file="translated_chapters/001.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(
            prompt_tokens=1000,
            completion_tokens=250,
            thought_tokens=50,
            cached_tokens=10,
            total_tokens=0,  # Legacy 0 total
            duration_seconds=15.5
        )
    )

    summary = compute_token_summary({"001": ch1})
    assert summary.total_chapters == 1
    assert summary.analyzed_chapters == 1
    assert summary.total_tokens == 1250  # 1000 + 250 fallback
    assert summary.prompt_tokens == 1000
    assert summary.completion_tokens == 250
    assert summary.total_duration_seconds == 15.5
    assert len(summary.chapter_rankings) == 1
    assert summary.chapter_rankings[0].total_tokens == 1250
    assert summary.chapter_rankings[0].status == "completed"


def test_compute_token_summary_stage_and_model_breakdown():
    # Chapter with step_usage
    ch1 = ChapterMetadata(
        chapter_id="ch_001",
        chapter_num=1,
        source_file="raw_chapters/001.txt",
        source_sha256="abc",
        output_file="translated_chapters/001.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(
            prompt_tokens=5000,
            completion_tokens=1000,
            total_tokens=6000,
            duration_seconds=45.0,
            step_usage=[
                StepTokenUsage(
                    stage=PipelineStage.DRAFTING,
                    model="gemini-3.1-flash-lite",
                    duration_seconds=30.0,
                    usage=TokenUsage(
                        input_tokens=3000,
                        output_tokens=800,
                        thought_tokens=500,
                        total_tokens=3800
                    )
                ),
                StepTokenUsage(
                    stage=PipelineStage.CRITIQUE,
                    model="gemma-4-26b-a4b-it",
                    duration_seconds=15.0,
                    usage=TokenUsage(
                        input_tokens=2000,
                        output_tokens=200,
                        thought_tokens=50,
                        cached_tokens=100,
                        total_tokens=2200
                    )
                )
            ]
        )
    )

    ch2 = ChapterMetadata(
        chapter_id="ch_002",
        chapter_num=2,
        source_file="raw_chapters/002.txt",
        source_sha256="def",
        output_file="translated_chapters/002.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(
            prompt_tokens=2000,
            completion_tokens=500,
            total_tokens=2500,
            duration_seconds=20.0,
            step_usage=[
                StepTokenUsage(
                    stage=PipelineStage.CRITIQUE,
                    model="gemma-4-26b-a4b-it",
                    duration_seconds=20.0,
                    usage=TokenUsage(
                        input_tokens=2000,
                        output_tokens=500,
                        total_tokens=2500
                    )
                )
            ]
        )
    )

    summary = compute_token_summary({"001": ch1, "002": ch2})
    assert summary.total_chapters == 2
    assert summary.total_tokens == 8500
    assert summary.total_duration_seconds == 65.0
    assert summary.avg_tokens_per_chapter == 4250.0

    # Verify stage breakdown
    assert len(summary.stage_metrics) == 2
    # Critique: 2200 + 2500 = 4700 tokens
    # Drafting: 3800 tokens
    assert summary.stage_metrics[0].stage == "critique"
    assert summary.stage_metrics[0].calls == 2
    assert summary.stage_metrics[0].total_tokens == 4700
    assert summary.stage_metrics[0].duration_seconds == 35.0
    assert summary.stage_metrics[0].avg_duration == 17.5

    assert summary.stage_metrics[1].stage == "drafting"
    assert summary.stage_metrics[1].calls == 1
    assert summary.stage_metrics[1].total_tokens == 3800

    # Verify model breakdown
    assert len(summary.model_metrics) == 2
    # gemma-4-26b-a4b-it: 2200 + 2500 = 4700 tokens
    # gemini-3.1-flash-lite: 3800 tokens
    assert summary.model_metrics[0].model == "gemma-4-26b-a4b-it"
    assert summary.model_metrics[0].calls == 2
    assert summary.model_metrics[0].total_tokens == 4700

    assert summary.model_metrics[1].model == "gemini-3.1-flash-lite"
    assert summary.model_metrics[1].calls == 1
    assert summary.model_metrics[1].total_tokens == 3800

    # Verify rankings: ch_001 (6000) > ch_002 (2500)
    assert summary.chapter_rankings[0].chapter_id == "ch_001"
    assert summary.chapter_rankings[1].chapter_id == "ch_002"
