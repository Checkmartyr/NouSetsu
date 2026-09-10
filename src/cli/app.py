"""CLI entry point for Novel Translation Agent."""
import argparse
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import dotenv
from src.batch.runner import BatchRunner
from src.storage.repository import NovelRepository, ProjectRegistry
from src.tui.app import NovelAgentApp

dotenv.load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def cmd_init(args: argparse.Namespace) -> None:
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    source_lang = args.source_lang or os.environ.get("SOURCE_LANG", "auto")
    target_lang = args.target_lang or os.environ.get("TARGET_LANG", "English")
    bible = repo.initialize_project(
        title=args.title,
        source_lang=source_lang,
        target_lang=target_lang,
        raw_dir=getattr(args, "raw_dir", "raw_chapters"),
        output_dir=getattr(args, "output_dir", "translated_chapters"),
        model_name=getattr(args, "model", "gemini-2.5-pro")
    )
    console.print(Panel.fit(
        f"[bold green]Novel Project Initialized![/]\n"
        f"Title: [cyan]{bible.title}[/]\n"
        f"Languages: [yellow]{bible.source_language} -> {bible.target_language}[/]\n"
        f"Location: [dim]{repo.root_dir}[/]\n"
        f"Config: [dim]{repo.config_file_path()}[/]\n"
        f"Bible: [dim]{repo.bible_file_path()}[/]",
        title="Success",
        border_style="green"
    ))


def cmd_batch(args: argparse.Namespace) -> None:
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    cfg = repo.load_config()
    if args.source_lang or args.target_lang:
        src_lang = args.source_lang
        if src_lang and src_lang.lower() in ["auto", "autodetect", "detect"]:
            src_lang = "Auto"
        repo.set_languages(source_lang=src_lang, target_lang=args.target_lang)
    runner = BatchRunner(
        repo,
        model_name=args.model,
        auto_update_bible=getattr(args, "auto_update_bible", None),
        max_tpm=getattr(args, "max_tpm", None),
        max_rpm=getattr(args, "max_rpm", None),
        console=console
    )
    input_path = Path(args.input_dir) if args.input_dir != "raw_chapters" else cfg.get_raw_path(repo.root_dir)
    output_path = Path(args.output_dir) if args.output_dir != "translated_chapters" else cfg.get_output_path(repo.root_dir)

    import signal

    def sigint_handler(sig, frame):
        console.print("\n[bold yellow]🛑 Stop requested by user (Ctrl+C)... halting cleanly and preserving checkpoints.[/]")
        runner.stop()

    prev_handler = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, sigint_handler)
    except Exception:
        # Some environments (e.g. non-main thread) may not permit setting signal
        pass

    try:
        runner.run_batch(
            input_dir=input_path,
            output_dir=output_path,
            limit=args.limit,
            force_retranslate=args.force
        )
    finally:
        try:
            signal.signal(signal.SIGINT, prev_handler)
        except Exception:
            pass


def cmd_tui(args: argparse.Namespace) -> None:
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    if getattr(args, "source_lang", None) or getattr(args, "target_lang", None):
        repo.set_languages(source_lang=args.source_lang, target_lang=args.target_lang)
    app = NovelAgentApp(
        input_dir=getattr(args, "input_dir", None),
        output_dir=getattr(args, "output_dir", None),
        model_name=getattr(args, "model", None),
        project_dir=project_dir
    )
    app.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Document-Level Novel Translation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    default_src = os.environ.get("SOURCE_LANG", "Japanese")
    default_tgt = os.environ.get("TARGET_LANG", "English")

    # init
    p_init = subparsers.add_parser("init", help="Initialize novel project and Novel Bible")
    p_init.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_init.add_argument("--title", default="Untitled Novel", help="Novel series title")
    p_init.add_argument("--source-lang", default=default_src, help="Source language (e.g. Japanese, Chinese, Korean)")
    p_init.add_argument("--target-lang", default=default_tgt, help="Target language (e.g. English, Spanish)")

    # batch
    p_batch = subparsers.add_parser("batch", help="Run folder-to-folder automated batch translation")
    p_batch.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_batch.add_argument("--input-dir", "-i", default="raw_chapters", help="Folder containing raw chapters")
    p_batch.add_argument("--output-dir", "-o", default="translated_chapters", help="Folder for translated output")
    p_batch.add_argument("--source-lang", default=None, help="Override source language")
    p_batch.add_argument("--target-lang", default=None, help="Override target language")
    p_batch.add_argument("--model", "-m", default=os.environ.get("DEFAULT_MODEL", "gemini-2.5-pro"), help="LLM model name")
    p_batch.add_argument("--limit", "-l", type=int, default=None, help="Maximum number of chapters to process")
    p_batch.add_argument("--force", "-f", action="store_true", help="Force re-translate completed chapters")
    p_batch.add_argument("--auto-update-bible", action=argparse.BooleanOptionalAction, default=None, help="Automatically merge new characters/terms into Novel Bible")
    p_batch.add_argument("--max-tpm", type=int, default=None, help="Max tokens per minute rate limit quota (default: 16000)")
    p_batch.add_argument("--max-rpm", type=int, default=None, help="Max requests per minute rate limit quota (default: 60)")

    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Textual TUI dashboard")
    p_tui.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_tui.add_argument("--input-dir", "-i", default=None, help="Folder containing raw chapters")
    p_tui.add_argument("--output-dir", "-o", default=None, help="Folder for translated output")
    p_tui.add_argument("--source-lang", default=None, help="Override source language")
    p_tui.add_argument("--target-lang", default=None, help="Override target language")
    p_tui.add_argument("--model", "-m", default=os.environ.get("DEFAULT_MODEL", "gemini-2.5-pro"), help="LLM model name")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "tui":
        cmd_tui(args)
    else:
        # Default behavior when no subcommand is provided: launch TUI if project/raw_chapters exists
        reg = ProjectRegistry()
        last_proj = reg.get_last_active_project()
        if last_proj or Path("raw_chapters").exists() or Path(".novel").exists() or Path("project").exists() or Path("projects").exists():
            cmd_tui(argparse.Namespace(
                project_dir=str(last_proj) if last_proj else ".",
                input_dir=None,
                output_dir=None,
                model=getattr(args, "model", os.environ.get("DEFAULT_MODEL", "gemini-2.5-pro")),
                source_lang=None,
                target_lang=None
            ))
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
