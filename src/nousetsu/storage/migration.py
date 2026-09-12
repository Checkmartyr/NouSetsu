"""Migration module for upgrading legacy Novel Bible summaries to 3-tier hierarchy."""
from typing import Any, Dict, List, Optional
from pathlib import Path
from nousetsu.models.bible import ArcSummary, ChapterSummary, NovelBible
from nousetsu.storage.repository import NovelRepository


KNOWN_NOVEL_PROFILES = {
    "villainess": {
        "title": "The Villainess",
        "whole_story_summary": (
            "Reincarnated into the novel's world, Ifia strives to survive alongside the powerful 'villainess' Amelia Barlen. "
            "After surviving dangerous maritime trials, the two return to the Sith Empire, where their bond deepens amidst fierce "
            "political turmoil, broken royal engagements, and court conspiracies. When the Rossword royalty's illicit experiments "
            "with auctioned magic plants unleash demonic outbreaks across the realm, Amelia and Ifia are thrust onto the front lines "
            "of an exorcism crisis in Dalva, fighting to expose royal corruption and secure Amelia's path to the throne."
        ),
        "arcs": {
            "Villainess_04": {
                "title": "Homeland Return & Royal Strife",
                "synopsis": (
                    "Following their voyage at sea, Ifia and Amelia return to the Sith Empire. As Ifia navigates system missions "
                    "to deepen her bond with Amelia, the pair becomes entangled in imperial politics, Amelia's broken royal "
                    "engagement, and the dangerous aftermath of magic plants auctioned at Kamus which the Rossword royalty "
                    "misused to attempt demon summoning."
                ),
                "core_conflict": (
                    "Navigate imperial political intrigue and prevent catastrophic fallout from royal demon summoning while "
                    "solidifying Amelia's succession standing."
                ),
                "status": "completed",
                "key_milestones": [
                    "Arrival of the Sith Empire fleet in the homeland",
                    "System bond missions and deepening emotional intimacy between Ifia and Amelia",
                    "Kamus magic plant auctions and commercial expansion",
                    "Formal severance of engagement between Amelia Barlen and Prince Carloy",
                    "Discovery that auctioned magic plants were weaponized for demon summoning by Rossword royalty"
                ]
            },
            "Villainess_05": {
                "title": "The Duller Exorcism",
                "synopsis": (
                    "Amelia is ordered by the King on a perilous exorcism mission in Dalva to deal with demonic outbreaks caused "
                    "by magic plants. Accompanied by Ifia and joined by Saint Tiffany and Church officials, they infiltrate "
                    "Count Duller's opulent mansion only for the possessed Count to violently mutate into a voracious demon."
                ),
                "core_conflict": (
                    "Exorcise the voracious demon possessing Count Duller, protect the church contingent, and counter the Rossword Dynasty's political trap."
                ),
                "status": "active",
                "key_milestones": [
                    "King's mandate forcing Amelia into the Dalva exorcism operation",
                    "Arrival in Dalwa and rendezvous with Saint Tiffany",
                    "March on Count Duller's gaudy mansion",
                    "Demonic manifestation: Count Duller breaks restraints and sprouts horns"
                ]
            }
        }
    }
}


def migrate_novel_summaries(
    repo: NovelRepository,
    title_override: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Migrate a novel project's summary system to the 3-tier hierarchy.
    1. Re-detects all folder scopes and chapters.
    2. Identifies concluded volumes and constructs archived ArcSummary records.
    3. Anchors active ArcSummary with complete start_chapter and key milestones.
    4. Generates or populates whole_story_summary macro progression.
    5. Synchronizes NovelBible and .novel/summaries/arcs/ on disk.
    """
    cfg = repo.load_config()
    bible = repo.load_bible()

    # Detect known profile
    root_name = repo.root_dir.name.lower()
    is_villainess = "villainess" in root_name or "villainess" in str(bible.title).lower() or any(
        "villainess" in (s.folder or "").lower() for s in bible.summaries
    )
    profile = KNOWN_NOVEL_PROFILES.get("villainess") if is_villainess else None

    # Title resolution
    if title_override:
        cfg.title = title_override
        bible.title = title_override
    elif profile and (not cfg.title or cfg.title in ["Ascendance of a Bookworm", "Untitled Novel"]):
        cfg.title = profile["title"]
        bible.title = profile["title"]

    all_by_folder = repo.get_all_summaries_by_folder()
    folder_order = repo.get_folder_order()
    if not folder_order:
        folder_order = list(all_by_folder.keys())

    archived_arcs: List[ArcSummary] = []
    active_arc: Optional[ArcSummary] = None

    # Determine which folders are completed and which is active
    active_folder = cfg.raw_dir if cfg.raw_dir in all_by_folder else (folder_order[-1] if folder_order else None)

    current_arc_num = 1
    for folder in folder_order:
        f_sums = all_by_folder.get(folder, [])
        if not f_sums:
            continue

        start_ch = min(s.chapter_num for s in f_sums)
        end_ch = max(s.chapter_num for s in f_sums)
        is_active = (folder == active_folder)

        # Check if folder matches a known profile
        folder_meta = profile["arcs"].get(folder) if profile and profile.get("arcs") else None

        if folder_meta:
            arc_title = folder_meta["title"]
            arc_synopsis = folder_meta["synopsis"]
            arc_conflict = folder_meta["core_conflict"]
            arc_status = "active" if is_active else folder_meta.get("status", "completed")
            arc_milestones = list(folder_meta.get("key_milestones", []))
        else:
            arc_title = f"{folder} Arc"
            arc_synopsis = f"Story progression across chapters {start_ch} to {end_ch}."
            arc_conflict = "Navigating challenges and resolving conflicts in volume."
            arc_status = "active" if is_active else "completed"
            arc_milestones = [e for s in f_sums[-3:] for e in s.key_events][:5]

        arc_obj = ArcSummary(
            arc_id=f"arc_{current_arc_num:04d}",
            arc_num=current_arc_num,
            title=arc_title,
            synopsis=arc_synopsis,
            core_conflict=arc_conflict,
            status=arc_status,
            start_chapter=start_ch,
            end_chapter=end_ch if arc_status == "completed" else end_ch,
            folder=folder,
            key_milestones=arc_milestones
        )

        if arc_status == "completed":
            archived_arcs.append(arc_obj)
        else:
            active_arc = arc_obj

        current_arc_num += 1

    # Macro Whole Story Summary
    if not bible.whole_story_summary or bible.whole_story_summary == "Initial world setup.":
        if profile and profile.get("whole_story_summary"):
            bible.whole_story_summary = profile["whole_story_summary"]
        else:
            parts = [f"In {a.title}: {a.synopsis}" for a in archived_arcs]
            if active_arc:
                parts.append(f"Currently in {active_arc.title}: {active_arc.synopsis}")
            bible.whole_story_summary = " ".join(parts)

    bible.archived_arcs = archived_arcs
    bible.active_arc = active_arc

    changes = {
        "title": bible.title,
        "whole_story_summary": bible.whole_story_summary,
        "archived_arcs": [a.model_dump() for a in archived_arcs],
        "active_arc": active_arc.model_dump() if active_arc else None,
        "folders_migrated": folder_order,
        "total_chapters": len(bible.summaries)
    }

    if not dry_run:
        # Save updated config
        repo.save_config(cfg)

        # Clear out previous stale arc files in arcs_dir to ensure clean numbering
        if repo.arcs_dir.exists():
            for old_f in repo.arcs_dir.glob("arc_*.json"):
                try:
                    old_f.unlink()
                except Exception:
                    pass

        # Save bible and sync new arc files
        repo.save_bible(bible)

    return changes
