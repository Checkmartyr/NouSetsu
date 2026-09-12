"""Repository for persisting Novel Bible, metadata, checkpoints, and translations."""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
from nousetsu.models.bible import ChapterSummary, CharacterProfile, GlossaryItem, NovelBible, StyleGuide
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, ProjectMetadataDocument, StageStatus
from nousetsu.utils.language import detect_language_from_dir


class ProjectRegistry:
    """Tracks known and discovered novel translation projects."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.is_custom_storage = storage_dir is not None
        reg_env = os.environ.get("NOVEL_REGISTRY_DIR")
        default_dir = Path(reg_env) if reg_env else (Path.home() / ".novel_agent")
        self.storage_dir = storage_dir or default_dir
        self.storage_file = self.storage_dir / "projects.json"

    def _load_raw(self) -> dict:
        if not self.storage_file.exists():
            return {"last_active": None, "projects": []}
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    return {"last_active": None, "projects": content}
                elif isinstance(content, dict):
                    return {
                        "last_active": content.get("last_active"),
                        "projects": content.get("projects", [])
                    }
        except Exception:
            pass
        return {"last_active": None, "projects": []}

    def _save_raw(self, data: dict) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_data(self) -> List[str]:
        raw = self._load_raw()
        paths = raw.get("projects", [])
        if not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR"):
            return [p for p in paths if "pytest" not in p and "Temp" not in p]
        return paths

    def _save_data(self, paths: List[str]) -> None:
        raw = self._load_raw()
        raw["projects"] = paths
        self._save_raw(raw)

    def get_last_active_project(self) -> Optional[Path]:
        """Retrieve the most recently active project path if valid."""
        if os.environ.get("PYTEST_CURRENT_TEST") and not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR"):
            return None
        raw = self._load_raw()
        last_str = raw.get("last_active")
        if last_str:
            p = Path(last_str)
            if p.exists() and (p / ".novel").exists():
                return p.resolve()
        return None

    def set_last_active_project(self, project_path: Path) -> None:
        """Persist the currently active project path."""
        if os.environ.get("PYTEST_CURRENT_TEST") and not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR"):
            return
        resolved = str(Path(project_path).resolve())
        if not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR") and ("pytest" in resolved or "Temp" in resolved):
            return
        raw = self._load_raw()
        raw["last_active"] = resolved
        if resolved not in raw["projects"]:
            raw["projects"].append(resolved)
        self._save_raw(raw)

    def register_project(self, project_path: Path) -> None:
        """Register a novel translation project in the global registry."""
        if os.environ.get("PYTEST_CURRENT_TEST") and not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR"):
            return
        resolved = str(Path(project_path).resolve())
        if not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR") and ("pytest" in resolved or "Temp" in resolved):
            return
        paths = self._load_data()
        if resolved not in paths:
            paths.append(resolved)
            self._save_data(paths)

    def list_projects(self) -> List[dict]:
        """Return list of project metadata for all known and discoverable projects."""
        paths = self._load_data()
        
        # Auto-discover current working directory, projects/, and project/ subdirectories if not under isolated test
        is_isolated_test = bool(os.environ.get("PYTEST_CURRENT_TEST") and not self.is_custom_storage and not os.environ.get("NOVEL_REGISTRY_DIR"))
        if not is_isolated_test:
            cwd = Path.cwd().resolve()
            if str(cwd) not in paths and (cwd / ".novel").exists():
                paths.append(str(cwd))

            for folder_name in ["projects", "project"]:
                projects_dir = cwd / folder_name
                if projects_dir.exists() and projects_dir.is_dir():
                    for child in projects_dir.iterdir():
                        if child.is_dir() and (child / ".novel").exists():
                            p_str = str(child.resolve())
                            if p_str not in paths:
                                paths.append(p_str)

        results = []
        valid_paths = []
        for p_str in paths:
            p = Path(p_str)
            if not p.exists() or not (p / ".novel").exists():
                continue
            valid_paths.append(p_str)
            repo = NovelRepository(p)
            cfg = repo.load_config()
            bible = repo.load_bible()
            results.append({
                "path": p_str,
                "title": cfg.title if cfg.title != "Untitled Novel" else bible.title,
                "source_language": bible.source_language,
                "target_language": bible.target_language,
                "raw_dir": str(cfg.get_raw_path(p)),
                "output_dir": str(cfg.get_output_path(p)),
                "model_name": cfg.model_name
            })

        if len(valid_paths) != len(paths):
            self._save_data(valid_paths)

        return results


class NovelRepository:
    """Manages file storage for a novel translation project."""

    def __init__(self, root_dir: Path | str = Path(".")):
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.novel_dir = self.root_dir / ".novel"
        self.bible_dir = self.novel_dir / "bible"
        self.summaries_dir = self.novel_dir / "summaries"

    def config_file_path(self) -> Path:
        return self.novel_dir / "config.yaml"

    def load_config(self) -> ProjectConfig:
        """Load project configuration or return default."""
        path = self.config_file_path()
        if not path.exists():
            # Fallback to bible or default
            bible = self.load_bible()
            return ProjectConfig(
                title=bible.title,
                source_language=bible.source_language,
                target_language=bible.target_language
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return ProjectConfig.model_validate(data)
        except Exception:
            return ProjectConfig()

    def save_config(self, config: ProjectConfig) -> None:
        """Save project configuration to .novel/config.yaml."""
        self.novel_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file_path(), "w", encoding="utf-8") as f:
            yaml.safe_dump(config.model_dump(), f, allow_unicode=True, sort_keys=False)

    def initialize_project(
        self,
        title: str = "Ascendance of a Bookworm",
        source_lang: str = "English",
        target_lang: str = "Thai",
        raw_dir: str = "raw_chapters",
        output_dir: str = "translated_chapters",
        model_name: Optional[str] = None,
        fallback_model: Optional[str] = None,
        extractor_model: Optional[str] = None,
        drafter_model: Optional[str] = None,
        critic_model: Optional[str] = None,
        polisher_model: Optional[str] = None,
        chronicler_model: Optional[str] = None,
        genre: str = "general"
    ) -> NovelBible:
        """Create project folder structure, config, and default Novel Bible."""
        self.bible_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.root_dir / raw_dir
        raw_path.mkdir(parents=True, exist_ok=True)
        (self.root_dir / output_dir).mkdir(parents=True, exist_ok=True)

        # Auto-detect language if requested or empty
        if (not source_lang) or source_lang.strip().lower() in ["auto", "autodetect", "detect", "unknown"]:
            source_lang = detect_language_from_dir(raw_path, default="Japanese")

        # Auto-detect genre if requested
        resolved_genre = genre
        if (not resolved_genre) or resolved_genre.strip().lower() in ["auto", "detect"]:
            from nousetsu.utils.genre import detect_genre
            # Check raw chapters
            sample_text = ""
            for rf in raw_path.glob("*.txt"):
                try:
                    sample_text += rf.read_text(encoding="utf-8")[:3000] + "\n"
                    if len(sample_text) >= 10000:
                        break
                except Exception:
                    pass
            resolved_genre = detect_genre(sample_text) if sample_text else "general"

        config = ProjectConfig(
            title=title,
            source_language=source_lang,
            target_language=target_lang,
            raw_dir=raw_dir,
            output_dir=output_dir,
            model_name=model_name,
            fallback_model=fallback_model,
            extractor_model=extractor_model,
            drafter_model=drafter_model,
            critic_model=critic_model,
            polisher_model=polisher_model,
            chronicler_model=chronicler_model,
            genre=resolved_genre
        )
        self.save_config(config)

        bible = NovelBible(
            title=title,
            source_language=source_lang,
            target_language=target_lang,
            genre=resolved_genre,
            characters=[],
            glossary=[],
            style_guide=StyleGuide(),
            summaries=[]
        )
        self.save_bible(bible)

        # Register in global project registry
        ProjectRegistry().register_project(self.root_dir)

        return bible

    def discover_folders(self) -> List[Tuple[str, str, int]]:
        """Discover candidate raw translation folders and their matching output folders in project root.

        Returns list of (raw_folder_rel, output_folder_rel, chapter_count) sorted naturally.
        """
        results: List[Tuple[str, str, int]] = []
        ignored_names = {
            ".novel", ".git", ".github", ".venv", "venv", "__pycache__",
            "node_modules", "target", "build", "dist", ".pytest_cache"
        }
        cfg = self.load_config()

        if not self.root_dir.exists():
            return results

        for child in self.root_dir.iterdir():
            if not child.is_dir() or child.name in ignored_names:
                continue
            # Ignore folders known to be output folders
            lname = child.name.lower()
            if lname.endswith("_th") or lname.endswith("_trans") or lname.endswith("_out") or lname == "translated_chapters":
                continue

            # Check if directory contains text/markdown chapters
            chapter_files = [f for f in child.iterdir() if f.is_file() and f.suffix.lower() in [".txt", ".md"]]
            count = len(chapter_files)
            if count > 0:
                # Infer corresponding output folder
                out_name = f"{child.name}_th"
                if (self.root_dir / f"{child.name}_th").exists():
                    out_name = f"{child.name}_th"
                elif (self.root_dir / f"{child.name}_trans").exists():
                    out_name = f"{child.name}_trans"
                elif cfg.raw_dir in [child.name, str(child)] and cfg.output_dir:
                    out_name = Path(cfg.output_dir).name
                elif (self.root_dir / "translated_chapters").exists() and child.name == "raw_chapters":
                    out_name = "translated_chapters"

                results.append((child.name, out_name, count))

        from natsort import natsorted
        return natsorted(results, key=lambda r: r[0])

    def set_active_folder(self, raw_dir: str, output_dir: Optional[str] = None) -> ProjectConfig:
        """Update active input and output folder paths in config.yaml."""
        cfg = self.load_config()
        cfg.raw_dir = raw_dir
        if output_dir:
            cfg.output_dir = output_dir
        self.save_config(cfg)
        return cfg

    def get_folder_order(self) -> List[str]:
        """Return naturally sorted list of all active or historical volume/chapter folder names."""
        folders = set()
        for raw_folder, _, _ in self.discover_folders():
            folders.add(raw_folder)
        if self.summaries_dir.exists():
            for child in self.summaries_dir.iterdir():
                if child.is_dir():
                    folders.add(child.name)
        from natsort import natsorted
        return natsorted(list(folders))

    def get_all_summaries_by_folder(self) -> Dict[str, List[ChapterSummary]]:
        """Return all summaries grouped by their folder/volume scope."""
        bible = self.load_bible()
        grouped: Dict[str, List[ChapterSummary]] = {}
        for s in bible.summaries:
            fname = s.folder or "Default"
            if fname not in grouped:
                grouped[fname] = []
            grouped[fname].append(s)
        for fname in grouped:
            grouped[fname].sort(key=lambda s: s.chapter_num)
        return grouped

    def bible_file_path(self) -> Path:
        return self.bible_dir / "bible.yaml"

    def load_bible(self, folder: Optional[str] = None) -> NovelBible:
        """Load Novel Bible from YAML, and sync chapter summaries (with folder scoping)."""
        path = self.bible_file_path()
        if not path.exists():
            return self.initialize_project()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Load chapter summaries with folder scoping
        summaries: List[ChapterSummary] = []
        if self.summaries_dir.exists():
            # Check subfolders (e.g. summaries/Villainess_04/, summaries/Villainess_05/)
            for child in self.summaries_dir.iterdir():
                if child.is_dir():
                    for s_file in sorted(child.glob("chapter_*.json")):
                        try:
                            with open(s_file, "r", encoding="utf-8") as sf:
                                sm = ChapterSummary.model_validate(json.load(sf))
                                if not sm.folder:
                                    sm.folder = child.name
                                summaries.append(sm)
                        except Exception:
                            continue

            # Also load root-level chapter summaries (legacy or un-scoped)
            root_summaries: List[ChapterSummary] = []
            for s_file in sorted(self.summaries_dir.glob("chapter_*.json")):
                try:
                    with open(s_file, "r", encoding="utf-8") as sf:
                        sm = ChapterSummary.model_validate(json.load(sf))
                        root_summaries.append(sm)
                except Exception:
                    continue

            if root_summaries:
                raw_folder_name = None
                cfg_path = self.config_file_path()
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as cf:
                            cdata = yaml.safe_load(cf) or {}
                            if cdata.get("raw_dir"):
                                raw_folder_name = Path(cdata["raw_dir"]).name
                    except Exception:
                        pass
                # If no subfolder summaries exist yet and raw_folder_name is known, tag or migrate
                if not summaries and raw_folder_name and raw_folder_name not in ["raw_chapters", "."]:
                    for sm in root_summaries:
                        sm.folder = raw_folder_name
                        summaries.append(sm)
                else:
                    for sm in root_summaries:
                        if not any(existing.chapter_num == sm.chapter_num and (existing.folder == sm.folder or sm.folder is None) for existing in summaries):
                            summaries.append(sm)

        if summaries:
            data["summaries"] = [s.model_dump() for s in summaries]

        return NovelBible.model_validate(data)

    def save_bible(self, bible: NovelBible) -> None:
        """Save Novel Bible to YAML and sync chapter summaries into folder subdirectories."""
        self.bible_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

        data = bible.model_dump(exclude={"summaries"})
        with open(self.bible_file_path(), "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        # Save summaries as individual JSON records for fast rolling context
        for summary in bible.summaries:
            if summary.folder:
                target_dir = self.summaries_dir / summary.folder
                target_dir.mkdir(parents=True, exist_ok=True)
                s_file = target_dir / f"chapter_{summary.chapter_num:04d}.json"
            else:
                s_file = self.summaries_dir / f"chapter_{summary.chapter_num:04d}.json"
            with open(s_file, "w", encoding="utf-8") as f:
                json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)

    def update_bible_memory(
        self,
        new_characters: List[CharacterProfile],
        new_terms: List[GlossaryItem],
        summary: Optional[ChapterSummary],
        folder: Optional[str] = None
    ) -> NovelBible:
        """Atomically merge new characters, glossary items, and chapter summary into Bible, evolving existing entries."""
        bible = self.load_bible(folder=folder)

        for new_char in new_characters:
            existing = bible.find_character(new_char.name) or bible.find_character(new_char.original_name)
            if not existing:
                bible.characters.append(new_char)
            else:
                # Merge new aliases deduplicated
                for alias in new_char.aliases:
                    if alias and alias.lower() not in [a.lower() for a in existing.aliases]:
                        existing.aliases.append(alias)
                # Evolve voice if existing was default/neutral or blank and new is informative
                if (not existing.voice or existing.voice.lower() in ["neutral", "unspecified", "default"]) and new_char.voice and new_char.voice.lower() not in ["neutral", "unspecified", "default"]:
                    existing.voice = new_char.voice
                # Evolve role if existing was minor/unspecified and new is more specific
                if (not existing.role or existing.role.lower() in ["minor", "unspecified"]) and new_char.role and new_char.role.lower() in ["protagonist", "antagonist", "supporting"]:
                    existing.role = new_char.role
                # Evolve gender if unspecified
                if (not existing.gender or existing.gender.lower() in ["unspecified", "unknown"]) and new_char.gender and new_char.gender.lower() not in ["unspecified", "unknown"]:
                    existing.gender = new_char.gender
                # Merge relationships
                if new_char.relationships:
                    existing.relationships.update(new_char.relationships)

        for new_term in new_terms:
            existing_term = bible.find_term(new_term.source)
            if not existing_term:
                bible.glossary.append(new_term)
            else:
                # Enrich notes if existing was empty
                if not existing_term.notes and new_term.notes:
                    existing_term.notes = new_term.notes
                # Upgrade generic category
                if existing_term.category == "term" and new_term.category != "term":
                    existing_term.category = new_term.category

        if summary:
            if folder and not summary.folder:
                summary.folder = folder
            target_folder = summary.folder
            # Replace existing summary for same chapter within the same folder scope, else append
            bible.summaries = [
                s for s in bible.summaries
                if not (s.chapter_num == summary.chapter_num and (s.folder == target_folder or target_folder is None or s.folder is None))
            ]
            bible.summaries.append(summary)
            bible.summaries.sort(key=lambda s: (s.folder or "", s.chapter_num))

        self.save_bible(bible)
        return bible

    def set_languages(self, source_lang: Optional[str] = None, target_lang: Optional[str] = None) -> NovelBible:
        """Update source and/or target languages in both Novel Bible and ProjectConfig."""
        bible = self.load_bible()
        if source_lang:
            bible.source_language = source_lang
        if target_lang:
            bible.target_language = target_lang
        self.save_bible(bible)

        cfg = self.load_config()
        if source_lang:
            cfg.source_language = source_lang
        if target_lang:
            cfg.target_language = target_lang
        self.save_config(cfg)
        return bible

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def get_metafile_path(output_file: Path) -> Path:
        """Legacy metafile path is <output_file>.meta.json or <stem>.meta.json."""
        return output_file.with_name(f"{output_file.stem}.meta.json")

    def project_metadata_file_path(self) -> Path:
        """Single consolidated metadata file path for the project."""
        return self.novel_dir / "metadata.json"

    def load_project_metadata_doc(self) -> ProjectMetadataDocument:
        """Load the project-level metadata document, initializing default if absent."""
        path = self.project_metadata_file_path()
        if not path.exists():
            return ProjectMetadataDocument()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ProjectMetadataDocument.model_validate(data)
        except Exception:
            return ProjectMetadataDocument()

    def save_project_metadata_doc(self, doc: ProjectMetadataDocument) -> None:
        """Save the project-level metadata document to .novel/metadata.json."""
        self.novel_dir.mkdir(parents=True, exist_ok=True)
        path = self.project_metadata_file_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc.model_dump(), f, indent=2, ensure_ascii=False)

    def load_all_metadata(self) -> Dict[str, ChapterMetadata]:
        """Return all chapter metadata for this project in a single fast read."""
        doc = self.load_project_metadata_doc()
        return doc.chapters

    def load_metadata(self, output_file: Path) -> Optional[ChapterMetadata]:
        """Load chapter metadata by composite folder/stem or stem from single project metadata file."""
        stem = output_file.stem
        folder_prefix = f"{output_file.parent.name}/{stem}"
        doc = self.load_project_metadata_doc()

        # 1. Composite key takes highest precedence for multi-folder isolation
        if folder_prefix in doc.chapters:
            return doc.chapters[folder_prefix]

        # 2. Match by bare stem
        if stem in doc.chapters:
            return doc.chapters[stem]

        # 3. Check by filename as fallback
        if output_file.name in doc.chapters:
            return doc.chapters[output_file.name]

        # Legacy fallback: check for individual <stem>.meta.json in output directory
        legacy_meta_path = self.get_metafile_path(output_file)
        if legacy_meta_path.exists():
            try:
                with open(legacy_meta_path, "r", encoding="utf-8") as f:
                    meta = ChapterMetadata.model_validate(json.load(f))
                    # Auto-migrate into project metadata document
                    doc.chapters[folder_prefix] = meta
                    doc.chapters[stem] = meta
                    self.save_project_metadata_doc(doc)
                    return meta
            except Exception:
                pass

        return None

    def save_metadata(self, metadata: ChapterMetadata, output_file: Path) -> Path:
        """Save chapter metadata into the single project metadata file with composite and stem keys."""
        stem = output_file.stem
        folder_prefix = f"{output_file.parent.name}/{stem}"
        doc = self.load_project_metadata_doc()
        doc.chapters[folder_prefix] = metadata
        doc.chapters[stem] = metadata
        self.save_project_metadata_doc(doc)
        return self.project_metadata_file_path()
