"""Chronicler agent for narrative continuity, summary generation, and metadata compilation."""
import json
import re
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.llm import extract_text_from_message, get_llm
from src.models.bible import ChapterSummary, CharacterProfile, GlossaryItem, NovelBible
from src.models.metadata import (
    ChapterMetadata,
    CheckpointData,
    PipelineStage,
    QualityAudit,
    StageArtifacts,
    StageStatus,
    TranslationStats,
)
from src.prompts.templates import CHRONICLER_SYSTEM_PROMPT


class ChroniclerAgent:
    """Updates narrative memory, generates chapter summaries, and compiles metadata audit records."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.2)

    def chronicle(
        self,
        chapter_num: int,
        chapter_title: str,
        translated_text: str
    ) -> ChapterSummary:
        sys_msg = CHRONICLER_SYSTEM_PROMPT.format(
            chapter_num=chapter_num,
            chapter_title=chapter_title or f"Chapter {chapter_num}"
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Translated Chapter:\n{translated_text[:12000]}")
        ])

        raw_content = extract_text_from_message(response.content)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        content_to_parse = json_match.group(1) if json_match else raw_content

        try:
            parsed = json.loads(content_to_parse)
            parsed["chapter_num"] = chapter_num
            return ChapterSummary.model_validate(parsed)
        except Exception:
            return ChapterSummary(
                chapter_num=chapter_num,
                title=chapter_title or f"Chapter {chapter_num}",
                synopsis=f"Events of Chapter {chapter_num} concluded.",
                key_events=["Chapter concluded."],
                character_state_changes=[]
            )

    def assemble_metadata(
        self,
        chapter_id: str,
        chapter_num: int,
        source_file: str,
        source_sha256: str,
        output_file: str,
        source_text: str,
        final_text: str,
        model_name: str,
        duration_seconds: float,
        quality_audit: QualityAudit,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        draft_text: str,
        critique_notes: str,
        polished_text: str,
        status: StageStatus = StageStatus.COMPLETED
    ) -> ChapterMetadata:
        artifacts = StageArtifacts(
            extracted_terms=active_glossary,
            extracted_characters=active_characters,
            draft_text=draft_text,
            critique_notes=critique_notes,
            polished_text=polished_text
        )

        checkpoint = CheckpointData(
            status=status,
            last_completed_stage=PipelineStage.CHRONICLING if status == StageStatus.COMPLETED else PipelineStage.POLISHING,
            retry_count=0,
            last_error=None,
            stage_artifacts=artifacts
        )

        stats = TranslationStats(
            source_char_count=len(source_text),
            target_word_count=len(final_text.split()),
            prompt_tokens=int(len(source_text) * 1.3),
            completion_tokens=int(len(final_text.split()) * 1.4),
            duration_seconds=round(duration_seconds, 2)
        )

        return ChapterMetadata(
            chapter_id=chapter_id,
            chapter_num=chapter_num,
            source_file=source_file,
            source_sha256=source_sha256,
            output_file=output_file,
            model=model_name,
            checkpoint=checkpoint,
            stats=stats,
            quality_audit=quality_audit,
            entities_present=[c.name for c in active_characters],
            glossary_terms_applied=active_glossary,
            paragraph_alignments=[]
        )
