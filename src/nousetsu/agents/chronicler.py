"""Chronicler agent for narrative continuity, summary generation, and metadata compilation."""
import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import ChapterSummary, CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import (
    ChapterMetadata,
    CheckpointData,
    PipelineStage,
    QualityAudit,
    StageArtifacts,
    StageStatus,
    StepTokenUsage,
    TokenUsage,
    TranslationStats,
)
from nousetsu.prompts.templates import CHRONICLER_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.character_filter import filter_characters_for_scene
from nousetsu.utils.glossary_filter import filter_glossary_for_scene
from nousetsu.utils.translation_fallback import is_safety_block_exception


class ChroniclerAgent:
    """Updates narrative memory, generates chapter summaries, and compiles metadata audit records."""

    def __init__(self, model_name: str = "gemma-4-26b-a4b-it", fallback_model: Optional[str] = None):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=0.2)
        self.last_usage: TokenUsage = TokenUsage()
        self.safety_fallbacks_used: int = 0

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    def chronicle(
        self,
        chapter_num: int,
        chapter_title: str,
        translated_text: str,
        genre: Optional[str] = None,
        source_lang: Optional[str] = None,
        bible: Optional[NovelBible] = None,
        rag_context: Optional[List[Any]] = None,
        **kwargs: Any
    ) -> ChapterSummary:
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="chronicler",
            source_lang=source_lang,
            genre=genre or "general"
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        rag_section = ""
        if rag_context:
            formatted_lore = []
            for hit in rag_context:
                doc = hit.document if hasattr(hit, "document") else hit
                content = getattr(doc, "content", str(doc))
                title = getattr(doc, "title", "Prior Lore")
                formatted_lore.append(f"[{title}]: {content[:400]}")
            rag_section = "\nPrior Series Lore & Character Memory (via RAG):\n" + "\n".join(formatted_lore) + "\n"

        sys_msg = CHRONICLER_SYSTEM_PROMPT.format(
            chapter_num=chapter_num,
            chapter_title=chapter_title or f"Chapter {chapter_num}",
            skills_section=skills_section,
            rag_context_section=rag_section
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=f"Analyze and summarize this translated novel chapter for story lore and plot events:\n{translated_text[:12000]}")
            ])
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            if is_safety_block_exception(e):
                self.safety_fallbacks_used += 1
                logger.warning("⚠️ Chronicler blocked by safety filter on sensitive scene - assigning default chapter summary.")
                return ChapterSummary(
                    chapter_num=chapter_num,
                    title=chapter_title or f"Chapter {chapter_num}",
                    synopsis=f"Events of Chapter {chapter_num} concluded.",
                    key_events=["Chapter concluded."],
                    character_state_changes=[]
                )
            raise

        raw_content = extract_text_from_message(response.content)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        content_to_parse = json_match.group(1) if json_match else raw_content

        try:
            parsed = json.loads(content_to_parse)
            if "chapter_summary" in parsed and isinstance(parsed["chapter_summary"], dict):
                chap_data = parsed["chapter_summary"]
                chap_data["chapter_num"] = chapter_num
                if "arc_update" in parsed and not chap_data.get("arc_update"):
                    chap_data["arc_update"] = parsed["arc_update"]
                if "story_update" in parsed and not chap_data.get("story_update"):
                    chap_data["story_update"] = parsed["story_update"]
                return ChapterSummary.model_validate(chap_data)
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
        status: StageStatus = StageStatus.COMPLETED,
        step_usage: Optional[List[StepTokenUsage]] = None,
        safety_fallbacks_used: int = 0,
        subdivisions_count: int = 0
    ) -> ChapterMetadata:
        artifacts = StageArtifacts(
            extracted_terms=active_glossary,
            extracted_characters=active_characters,
            draft_text=draft_text,
            critique_notes=critique_notes,
            polished_text=polished_text,
            safety_fallbacks_used=safety_fallbacks_used,
            subdivisions_count=subdivisions_count
        )

        checkpoint = CheckpointData(
            status=status,
            last_completed_stage=PipelineStage.CHRONICLING if status == StageStatus.COMPLETED else PipelineStage.POLISHING,
            retry_count=0,
            last_error=None,
            stage_artifacts=artifacts
        )

        step_records = step_usage or []
        if step_records:
            prompt_tokens = sum(s.usage.input_tokens for s in step_records)
            completion_tokens = sum(s.usage.output_tokens for s in step_records)
            thought_tokens = sum(s.usage.thought_tokens for s in step_records)
            cached_tokens = sum(s.usage.cached_tokens for s in step_records)
            total_tokens = sum(s.usage.total_tokens for s in step_records)
        else:
            prompt_tokens = int(len(source_text) * 1.3)
            completion_tokens = int(len(final_text.split()) * 1.4)
            thought_tokens = 0
            cached_tokens = 0
            total_tokens = prompt_tokens + completion_tokens

        stats = TranslationStats(
            source_char_count=len(source_text),
            target_word_count=len(final_text.split()),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            thought_tokens=thought_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            duration_seconds=round(duration_seconds, 2),
            step_usage=step_records,
            safety_fallbacks_used=safety_fallbacks_used,
            subdivisions_count=subdivisions_count
        )

        present_chars = filter_characters_for_scene(
            characters=active_characters,
            source_text=source_text,
            target_text=final_text
        )

        present_glossary = filter_glossary_for_scene(
            glossary=active_glossary,
            source_text=source_text,
            fallback_on_empty=False
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
            entities_present=[c.name for c in present_chars],
            glossary_terms_applied=present_glossary,
            paragraph_alignments=[]
        )
