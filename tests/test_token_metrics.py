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


def test_compute_token_summary_folder_grouping_and_filtering():
    """Verify compute_token_summary handles folder grouping, deduplication, and folder filtering."""
    ch1 = ChapterMetadata(
        chapter_id="ch_001",
        chapter_num=1,
        source_file="Volume_01/001.txt",
        source_sha256="hash1",
        output_file="Volume_01_th/001.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(total_tokens=1000, prompt_tokens=800, completion_tokens=200, duration_seconds=10.0)
    )
    ch2 = ChapterMetadata(
        chapter_id="ch_002",
        chapter_num=2,
        source_file="Volume_01/002.txt",
        source_sha256="hash2",
        output_file="Volume_01_th/002.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(total_tokens=1500, prompt_tokens=1200, completion_tokens=300, duration_seconds=15.0)
    )
    ch3 = ChapterMetadata(
        chapter_id="ch_003",
        chapter_num=3,
        source_file="Volume_02/001.txt",
        source_sha256="hash3",
        output_file="Volume_02_th/001.md",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED),
        stats=TranslationStats(total_tokens=3000, prompt_tokens=2400, completion_tokens=600, duration_seconds=30.0)
    )

    # Simulate repository having duplicate composite & stem keys for ch1
    chapters_dict = {
        "Volume_01_th/001": ch1,
        "001": ch1,
        "Volume_01_th/002": ch2,
        "Volume_02_th/001": ch3,
    }

    # 1. Global summary across all folders
    summary_all = compute_token_summary(chapters_dict)
    assert summary_all.total_chapters == 3  # Deduplicated from 4 keys to 3
    assert summary_all.total_tokens == 5500  # 1000 + 1500 + 3000
    assert summary_all.total_duration_seconds == 55.0
    assert summary_all.available_folders == ["Volume_01", "Volume_02"]

    # Verify folder metrics
    assert len(summary_all.folder_metrics) == 2
    assert summary_all.folder_metrics[0].folder == "Volume_02"
    assert summary_all.folder_metrics[0].chapter_count == 1
    assert summary_all.folder_metrics[0].total_tokens == 3000

    assert summary_all.folder_metrics[1].folder == "Volume_01"
    assert summary_all.folder_metrics[1].chapter_count == 2
    assert summary_all.folder_metrics[1].total_tokens == 2500
    assert summary_all.folder_metrics[1].avg_tokens == 1250.0

    # 2. Filtered summary by Volume_01
    summary_v1 = compute_token_summary(chapters_dict, folder_filter="Volume_01")
    assert summary_v1.total_chapters == 2
    assert summary_v1.total_tokens == 2500
    assert summary_v1.total_duration_seconds == 25.0
    assert summary_v1.selected_folder == "Volume_01"
    assert len(summary_v1.chapter_rankings) == 2
    assert all(c.folder == "Volume_01" for c in summary_v1.chapter_rankings)
    assert len(summary_v1.folder_metrics) == 2

    # 3. Filtered summary by Volume_02
    summary_v2 = compute_token_summary(chapters_dict, folder_filter="Volume_02")
    assert summary_v2.total_chapters == 1
    assert summary_v2.total_tokens == 3000
    assert summary_v2.chapter_rankings[0].chapter_id == "ch_003"

