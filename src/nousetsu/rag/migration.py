"""Migration engine to backfill existing novel data into Hybrid Search RAG (LoreVault)."""
import logging
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from nousetsu.models.bible import ArcSummary, ChapterSummary, NovelBible
from nousetsu.rag.embeddings import EmbeddingClient
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument
from nousetsu.storage.repository import NovelRepository

logger = logging.getLogger(__name__)


class MigrationStats(BaseModel):
    """Statistics summarizing the RAG data migration."""
    summaries_indexed: int = Field(default=0, description="Chapter summaries indexed")
    arcs_indexed: int = Field(default=0, description="Story arcs indexed")
    characters_indexed: int = Field(default=0, description="Novel bible characters indexed")
    glossary_indexed: int = Field(default=0, description="Glossary items indexed")
    chunks_indexed: int = Field(default=0, description="Translated scene chunks indexed")
    total_indexed: int = Field(default=0, description="Total documents indexed")
    total_embedded: int = Field(default=0, description="Total dense embeddings generated")
    duration_seconds: float = Field(default=0.0, description="Migration execution time in seconds")
    folders_scanned: List[str] = Field(default_factory=list, description="Volume/folder names scanned")


def _extract_chapter_num_from_filename(filename: str) -> int:
    """Extract chapter number from filename like '001_Chapter 1.md' or 'chapter_0048.json'."""
    m = re.search(r"(\d+)", filename)
    return int(m.group(1)) if m else 0


def _build_summary_document(summary: ChapterSummary, folder: str) -> LoreDocument:
    """Format ChapterSummary into LoreDocument."""
    synopsis = summary.synopsis or ""
    key_events = summary.key_events or []
    shifts = summary.character_state_changes or []

    content = f"Synopsis: {synopsis}\nKey Events: {'; '.join(key_events)}"
    if shifts:
        content += f"\nCharacter Shifts: {'; '.join(shifts)}"

    title = f"[{folder}] Chapter {summary.chapter_num}: {summary.title}" if summary.title else f"[{folder}] Chapter {summary.chapter_num}"
    return LoreDocument(
        doc_id=f"summary:{folder}:{summary.chapter_num:04d}",
        doc_type=DocumentType.SUMMARY,
        chapter_num=summary.chapter_num,
        folder=folder,
        title=title,
        content=content.strip(),
        metadata={"type": "chapter_summary", "folder": folder, "chapter_num": summary.chapter_num}
    )


def _build_arc_document(arc: ArcSummary) -> LoreDocument:
    """Format ArcSummary into LoreDocument."""
    folder = arc.folder or "default"
    synopsis = arc.synopsis or ""
    conflict = arc.core_conflict or ""
    milestones = arc.key_milestones or []

    content = f"Arc Title: {arc.title}\nStatus: {arc.status} (Ch. {arc.start_chapter}-{arc.end_chapter})\nConflict: {conflict}\nSynopsis: {synopsis}\nMilestones: {'; '.join(milestones)}"
    return LoreDocument(
        doc_id=f"arc:{folder}:{arc.arc_num:04d}",
        doc_type=DocumentType.SUMMARY,
        chapter_num=arc.start_chapter,
        folder=arc.folder,
        title=f"Arc {arc.arc_num}: {arc.title}",
        content=content.strip(),
        metadata={"type": "arc_summary", "arc_num": arc.arc_num, "status": arc.status, "folder": arc.folder}
    )


def _build_character_document(char) -> LoreDocument:
    """Format NovelBible CharacterProfile into LoreDocument."""
    name_clean = char.name.strip().replace(" ", "_")
    lines = [f"Name: {char.name}", f"Original Name: {char.original_name}"]
    if char.aliases:
        lines.append(f"Aliases: {', '.join(char.aliases)}")
    if char.role:
        lines.append(f"Role: {char.role}")
    if char.gender:
        lines.append(f"Gender: {char.gender}")
    if char.voice:
        lines.append(f"Voice/Speech Quirks: {char.voice}")
    if char.relationships:
        rel_str = "; ".join(f"{k}: {v}" for k, v in char.relationships.items())
        lines.append(f"Relationships: {rel_str}")

    return LoreDocument(
        doc_id=f"character:{name_clean}",
        doc_type=DocumentType.CHARACTER,
        chapter_num=0,
        folder=None,
        title=f"Character: {char.name} ({char.original_name})",
        content="\n".join(lines),
        metadata={"type": "character", "name": char.name, "original_name": char.original_name, "role": char.role}
    )


def _build_glossary_document(term) -> LoreDocument:
    """Format NovelBible GlossaryItem into LoreDocument."""
    source_clean = term.source.strip().replace(" ", "_")
    lines = [f"Source Term: {term.source}", f"Target Translation: {term.target}"]
    if term.category:
        lines.append(f"Category: {term.category}")
    if term.notes:
        lines.append(f"Notes/Context: {term.notes}")

    return LoreDocument(
        doc_id=f"glossary:{source_clean}",
        doc_type=DocumentType.GLOSSARY,
        chapter_num=0,
        folder=None,
        title=f"Glossary: {term.source} -> {term.target}",
        content="\n".join(lines),
        metadata={"type": "glossary", "source": term.source, "target": term.target, "category": term.category}
    )


def _partition_scene_chunks(
    file_path: Path,
    folder: str,
    chapter_num: int,
    chunk_size_lines: int = 20
) -> List[LoreDocument]:
    """Read translated markdown and partition into ~20-line scene chunks."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return []

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return []

    title_stem = file_path.stem
    clean_title = re.sub(r"^\d+[\s_-]*", "", title_stem) or f"Chapter {chapter_num}"

    docs: List[LoreDocument] = []
    chunk_idx = 1
    for i in range(0, len(lines), chunk_size_lines):
        chunk_slice = lines[i:i + chunk_size_lines]
        if not chunk_slice:
            continue
        chunk_content = "\n".join(chunk_slice)
        docs.append(LoreDocument(
            doc_id=f"chunk:{folder}:{chapter_num:04d}:{chunk_idx:03d}",
            doc_type=DocumentType.CHUNK,
            chapter_num=chapter_num,
            folder=folder,
            title=f"[{folder}] {clean_title} (Part {chunk_idx})",
            content=chunk_content,
            metadata={"type": "scene_chunk", "folder": folder, "chapter_num": chapter_num, "chunk_idx": chunk_idx}
        ))
        chunk_idx += 1
    return docs


def migrate_project_to_rag(
    repository: NovelRepository,
    embedding_client: Optional[EmbeddingClient] = None,
    include_summaries: bool = True,
    include_arcs: bool = True,
    include_bible: bool = True,
    include_chunks: bool = True,
    folder_filter: Optional[str] = None,
    chunk_size_lines: int = 20,
    batch_size: int = 50,
    embed: bool = True,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> MigrationStats:
    """Migrate and backfill existing novel data from .novel into RAG SQLite knowledge store.
    
    Args:
        repository: NovelRepository instance.
        embedding_client: Optional EmbeddingClient for dense vector generation.
        include_summaries: Index chapter summaries from .novel/summaries/.
        include_arcs: Index story arcs from .novel/summaries/arcs/.
        include_bible: Index characters and glossary items from Novel Bible.
        include_chunks: Index translated scene chunks from volume output folders.
        folder_filter: Restrict migration to a specific volume folder name.
        chunk_size_lines: Line count per scene chunk (default: 20).
        batch_size: Batch size for database indexing and embeddings (default: 50).
        embed: Compute dense embeddings with EmbeddingClient (default: True).
        dry_run: Count and preview documents without modifying database.
        progress_callback: Optional callback receiving (stage_name, processed_count, total_count).
    
    Returns:
        MigrationStats with execution metrics.
    """
    start_time = time.time()
    stats = MigrationStats()
    docs_to_index: List[LoreDocument] = []
    scanned_folders: set[str] = set()

    # 1. Chapter Summaries
    if include_summaries and repository.summaries_dir.exists():
        for sub_dir in sorted(repository.summaries_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name == "arcs":
                continue
            folder_name = sub_dir.name
            if folder_filter and folder_name != folder_filter:
                continue
            scanned_folders.add(folder_name)

            for sum_file in sorted(sub_dir.glob("chapter_*.json")):
                try:
                    summary = ChapterSummary.model_validate_json(sum_file.read_text(encoding="utf-8"))
                    docs_to_index.append(_build_summary_document(summary, folder_name))
                    stats.summaries_indexed += 1
                except Exception as e:
                    logger.warning(f"Skipping corrupt summary file {sum_file}: {e}")

        # Also check root of summaries_dir for single-volume projects
        if not folder_filter:
            for sum_file in sorted(repository.summaries_dir.glob("chapter_*.json")):
                try:
                    summary = ChapterSummary.model_validate_json(sum_file.read_text(encoding="utf-8"))
                    folder_name = summary.folder or "default"
                    scanned_folders.add(folder_name)
                    docs_to_index.append(_build_summary_document(summary, folder_name))
                    stats.summaries_indexed += 1
                except Exception as e:
                    logger.warning(f"Skipping corrupt summary file {sum_file}: {e}")

    # 2. Story Arcs
    if include_arcs and repository.arcs_dir.exists():
        for arc_file in sorted(repository.arcs_dir.glob("arc_*.json")):
            try:
                arc = ArcSummary.model_validate_json(arc_file.read_text(encoding="utf-8"))
                if folder_filter and arc.folder and arc.folder != folder_filter:
                    continue
                docs_to_index.append(_build_arc_document(arc))
                stats.arcs_indexed += 1
            except Exception as e:
                logger.warning(f"Skipping corrupt arc file {arc_file}: {e}")

    # 3. Novel Bible Characters and Glossary
    if include_bible:
        try:
            bible = repository.load_bible()
            for char in bible.characters:
                docs_to_index.append(_build_character_document(char))
                stats.characters_indexed += 1
            for term in bible.glossary:
                docs_to_index.append(_build_glossary_document(term))
                stats.glossary_indexed += 1
        except Exception as e:
            logger.warning(f"Failed to load Novel Bible for RAG indexing: {e}")

    # 4. Translated Scene Chunks
    if include_chunks:
        # Discover output folders
        candidate_dirs: List[tuple[str, Path]] = []
        if folder_filter:
            for cand_name in [f"{folder_filter}_th", f"{folder_filter}_trans", folder_filter]:
                cand_p = repository.root_dir / cand_name
                if cand_p.exists() and cand_p.is_dir():
                    candidate_dirs.append((folder_filter, cand_p))
                    break
        else:
            # Check for scanned folders matching output directory patterns
            for fld in sorted(scanned_folders):
                for cand_name in [f"{fld}_th", f"{fld}_trans", fld]:
                    cand_p = repository.root_dir / cand_name
                    if cand_p.exists() and cand_p.is_dir():
                        candidate_dirs.append((fld, cand_p))
                        break

            # Fallback to configured output directory if no volume directories matched
            cfg = repository.load_config()
            def_out = cfg.get_output_path(repository.root_dir)
            if def_out.exists() and not candidate_dirs:
                candidate_dirs.append(("default", def_out))

        for fld_name, out_p in candidate_dirs:
            scanned_folders.add(fld_name)
            for md_file in sorted(out_p.glob("*.md")):
                ch_num = _extract_chapter_num_from_filename(md_file.name)
                chunks = _partition_scene_chunks(md_file, fld_name, ch_num, chunk_size_lines)
                docs_to_index.extend(chunks)
                stats.chunks_indexed += len(chunks)

    stats.total_indexed = len(docs_to_index)
    stats.folders_scanned = sorted(scanned_folders)

    if dry_run or not docs_to_index:
        stats.duration_seconds = round(time.time() - start_time, 2)
        return stats

    # 5. Index into HybridSearchEngine
    engine: HybridSearchEngine = repository.get_rag_engine()
    total_docs = len(docs_to_index)
    can_embed = embed and embedding_client is not None and embedding_client.is_available

    for i in range(0, total_docs, batch_size):
        batch = docs_to_index[i:i + batch_size]
        batch_embeddings = None

        if can_embed:
            try:
                batch_embeddings = embedding_client.embed_documents([d.content for d in batch])
                valid_embs = sum(1 for e in batch_embeddings if e is not None)
                stats.total_embedded += valid_embs
            except Exception as e:
                logger.warning(f"Batch embedding generation failed during migration: {e}")
                batch_embeddings = None

        engine.index_documents(batch, batch_embeddings)

        if progress_callback:
            processed = min(i + batch_size, total_docs)
            progress_callback("indexing", processed, total_docs)

    stats.duration_seconds = round(time.time() - start_time, 2)
    return stats
