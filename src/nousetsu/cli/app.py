"""CLI entry point for Novel Translation Agent."""
import argparse
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import dotenv
from nousetsu import __version__
from nousetsu.batch.runner import BatchRunner
from nousetsu.storage.repository import NovelRepository, ProjectRegistry
from nousetsu.tui.app import NovelAgentApp

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
        model_name=getattr(args, "model", None),
        genre=getattr(args, "genre", "general")
    )
    console.print(Panel.fit(
        f"[bold green]Novel Project Initialized![/]\n"
        f"Title: [cyan]{bible.title}[/]\n"
        f"Genre: [magenta]{bible.genre}[/]\n"
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
    if getattr(args, "interactions", None) is not None:
        os.environ["NOVEL_USE_INTERACTIONS"] = "1" if args.interactions else "0"
    elif hasattr(cfg, "use_interactions_api"):
        os.environ["NOVEL_USE_INTERACTIONS"] = "1" if cfg.use_interactions_api else "0"

    if args.source_lang or args.target_lang:
        src_lang = args.source_lang
        if src_lang and src_lang.lower() in ["auto", "autodetect", "detect"]:
            src_lang = "Auto"
        repo.set_languages(source_lang=src_lang, target_lang=args.target_lang)
    runner = BatchRunner(
        repo,
        model_name=args.model,
        fallback_model=getattr(args, "fallback_model", None),
        extractor_model=getattr(args, "extractor_model", None),
        drafter_model=getattr(args, "drafter_model", None),
        critic_model=getattr(args, "critic_model", None),
        polisher_model=getattr(args, "polisher_model", None),
        chronicler_model=getattr(args, "chronicler_model", None),
        auto_update_bible=getattr(args, "auto_update_bible", None),
        max_tpm=getattr(args, "max_tpm", None),
        max_rpm=getattr(args, "max_rpm", None),
        max_review_loops=getattr(args, "max_loops", None),
        quality_threshold=getattr(args, "quality_threshold", None),
        genre=getattr(args, "genre", None),
        enable_chunking=getattr(args, "chunking", None),
        chunk_threshold_lines=getattr(args, "chunk_threshold_lines", None),
        target_chunk_lines=getattr(args, "target_chunk_lines", None),
        enable_rag=getattr(args, "rag", None),
        enable_rag_reranker=getattr(args, "rerank", None),
        console=console
    )
    folder_arg = getattr(args, "folder", None)
    if folder_arg:
        raw_cand = repo.root_dir / folder_arg
        if raw_cand.exists() and raw_cand.is_dir():
            input_path = raw_cand
            if args.output_dir and args.output_dir != "translated_chapters":
                output_path = Path(args.output_dir) if Path(args.output_dir).is_absolute() else (repo.root_dir / args.output_dir)
            else:
                out_cand_th = repo.root_dir / f"{folder_arg}_th"
                out_cand_tr = repo.root_dir / f"{folder_arg}_trans"
                output_path = out_cand_th if out_cand_th.exists() else (out_cand_tr if out_cand_tr.exists() else out_cand_th)
            repo.set_active_folder(raw_dir=folder_arg, output_dir=output_path.name)
        else:
            input_path = Path(args.input_dir) if args.input_dir != "raw_chapters" else cfg.get_raw_path(repo.root_dir)
            output_path = Path(args.output_dir) if args.output_dir != "translated_chapters" else cfg.get_output_path(repo.root_dir)
    else:
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
            force_retranslate=args.force,
            chapter_filter=getattr(args, "chapter", None)
        )
    finally:
        try:
            signal.signal(signal.SIGINT, prev_handler)
        except Exception:
            pass


def cmd_skills(args: argparse.Namespace) -> None:
    from rich.table import Table
    from nousetsu.skills.registry import SkillRegistry

    reg = SkillRegistry.get_instance()
    agent_filter = getattr(args, "agent", None)
    lang_filter = getattr(args, "source_lang", None)
    genre_filter = getattr(args, "genre", None)

    if agent_filter or lang_filter or genre_filter:
        skills = reg.get_active_skills(
            agent=agent_filter or "all",
            source_lang=lang_filter,
            genre=genre_filter
        )
        title = f"Active Agent Skills (Agent: {agent_filter or 'Any'}, Lang: {lang_filter or 'Any'}, Genre: {genre_filter or 'Any'})"
    else:
        skills = reg.list_skills()
        title = f"Registered Agent Skills ({len(skills)} Total)"

    table = Table(title=title, border_style="cyan")
    table.add_column("Agent", style="bold green", width=12)
    table.add_column("Skill Name", style="bold yellow")
    table.add_column("Title", style="white")
    table.add_column("Languages", style="dim cyan")
    table.add_column("Genres", style="magenta")
    table.add_column("Source", style="dim")

    for s in sorted(skills, key=lambda x: (x.agent, -x.priority, x.name)):
        table.add_row(
            s.agent.capitalize(),
            s.name,
            s.title,
            ", ".join(s.languages),
            ", ".join(s.genres),
            s.source
        )

    console.print(table)


def cmd_graph_info(args: argparse.Namespace) -> None:
    """Display active Procedural Graphs with Rich tree formatting."""
    from rich.panel import Panel
    from rich.tree import Tree
    from nousetsu.graph.procedural import get_default_drafter_graph, get_default_extractor_graph

    agent_filter = (getattr(args, "agent", None) or "all").lower()

    graphs_to_show = []
    if agent_filter in ["all", "extractor"]:
        graphs_to_show.append(("Extractor (Schriftdetektiv)", get_default_extractor_graph()))
    if agent_filter in ["all", "drafter"]:
        graphs_to_show.append(("Drafter (Wortschmied)", get_default_drafter_graph()))

    if not graphs_to_show:
        console.print(f"[yellow]No procedural graph found for agent '{args.agent}'. Use 'extractor', 'drafter', or 'all'.[/]")
        return

    for title, g in graphs_to_show:
        tree = Tree(f"[bold cyan]Procedural Graph: {title}[/] [dim]({g.graph_id})[/]")
        tree.add(f"[italic dim]{g.description}[/]")

        # Nodes
        nodes_branch = tree.add("[bold yellow]Nodes (V)[/]")
        for n_id, n in g.nodes.items():
            type_val = n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type)
            type_color = "green" if type_val == "ACTION" else "magenta"
            nodes_branch.add(f"[bold]{n.name}[/] [dim]({n.id})[/] - [{type_color}]{type_val}[/]: [dim]{n.description}[/]")

        # Edges
        edges_branch = tree.add("[bold green]Transitions & Execution Directives (E, \u03a6)[/]")
        for e in g.edges:
            cond_str = f" [cyan][When: {e.condition}][/]" if e.condition else ""
            edge_leaf = edges_branch.add(f"[bold]{e.source}[/] -> [bold]{e.target}[/]{cond_str}")
            edge_leaf.add(f"[white]Guidance:[/] {e.guidance}")
            if e.pitfalls:
                edge_leaf.add(f"[red bold]Pitfalls to Avoid:[/] {e.pitfalls}")

def cmd_narrative(args: argparse.Namespace) -> None:
    from rich.tree import Tree
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    bible = repo.load_bible()

    root_label = f"[bold cyan]📖 {bible.title}[/] [dim]({bible.source_language} -> {bible.target_language})[/]"
    tree = Tree(root_label)

    # 1. Macro: Whole Story
    story_branch = tree.add("[bold magenta]🌐 1. Global Story Progression (Macro)[/]")
    if bible.whole_story_summary:
        story_branch.add(f"[white]{bible.whole_story_summary}[/]")
    else:
        story_branch.add("[dim italic]No whole-story progression recorded yet.[/]")

    # 2. Meso: Story Arcs
    arcs_branch = tree.add("[bold yellow]📚 2. Story Arcs (Meso)[/]")
    all_arcs = bible.get_all_arcs()
    if all_arcs or bible.active_arc:
        if bible.active_arc:
            a = bible.active_arc
            act_node = arcs_branch.add(f"[bold green]▶ Arc {a.arc_num}: {a.title or 'Ongoing Arc'} [ACTIVE][/] [dim](From Ch. {a.start_chapter})[/]")
            if a.core_conflict:
                act_node.add(f"[yellow]Conflict:[/] {a.core_conflict}")
            if a.synopsis:
                act_node.add(f"[white]Summary:[/] {a.synopsis}")
            if a.key_milestones:
                act_node.add(f"[cyan]Milestones:[/] {', '.join(a.key_milestones)}")
        for arc in bible.archived_arcs:
            if bible.active_arc and arc.arc_num == bible.active_arc.arc_num:
                continue
            end_str = f" to {arc.end_chapter}" if arc.end_chapter else ""
            arc_node = arcs_branch.add(f"[dim]✓ Arc {arc.arc_num}: {arc.title} [COMPLETED] (Ch. {arc.start_chapter}{end_str})[/]")
            if arc.synopsis:
                arc_node.add(f"[dim]{arc.synopsis}[/]")
    else:
        arcs_branch.add("[dim italic]No story arcs identified yet.[/]")

    # 3. Micro: Chapter Summaries
    all_by_folder = repo.get_all_summaries_by_folder()
    if not all_by_folder and bible.summaries:
        all_by_folder = {"Default": bible.summaries}

    micro_branch = tree.add("[bold green]📄 3. Immediate Chapter Summaries (Micro)[/]")
    if all_by_folder:
        for folder_name, f_sums in all_by_folder.items():
            f_node = micro_branch.add(f"[bold cyan]📁 {folder_name}[/] [dim]({len(f_sums)} chapters)[/]")
            display_sums = f_sums[-5:] if len(f_sums) > 5 else f_sums
            if len(f_sums) > 5:
                f_node.add(f"[dim italic]... ({len(f_sums) - 5} earlier chapters omitted) ...[/]")
            for s in display_sums:
                ch_node = f_node.add(f"[bold]Chapter {s.chapter_num}[/] [dim]({s.title or 'Untitled'})[/]")
                ch_node.add(f"[white]{s.synopsis}[/]")
    else:
        micro_branch.add("[dim italic]No chapter summaries recorded yet.[/]")

    console.print(Panel(tree, border_style="cyan", padding=(1, 2)))


def cmd_migrate_summaries(args: argparse.Namespace) -> None:
    from rich.panel import Panel
    from rich.tree import Tree
    from nousetsu.storage.migration import migrate_novel_summaries

    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    dry_run = getattr(args, "dry_run", False)
    title_override = getattr(args, "title", None)

    console.print(f"[bold cyan]🔄 {'[DRY-RUN] ' if dry_run else ''}Migrating summary system for {repo.root_dir}...[/]")
    results = migrate_novel_summaries(repo=repo, title_override=title_override, dry_run=dry_run)

    tree = Tree(f"[bold green]✓ Migration Complete: {results['title']}[/]")
    tree.add(f"[magenta]Whole Story:[/] {results['whole_story_summary']}")

    arcs_node = tree.add(f"[yellow]Story Arcs ({len(results['archived_arcs'])} archived, 1 active):[/]")
    for a in results['archived_arcs']:
        arcs_node.add(f"[dim]✓ Arc {a['arc_num']}: {a['title']} [COMPLETED] (Ch. {a['start_chapter']}-{a['end_chapter']})[/]")
    if results['active_arc']:
        act = results['active_arc']
        act_node = arcs_node.add(f"[bold green]▶ Arc {act['arc_num']}: {act['title']} [ACTIVE] (From Ch. {act['start_chapter']})[/]")
        act_node.add(f"[yellow]Conflict:[/] {act['core_conflict']}")
        if act['key_milestones']:
            act_node.add(f"[cyan]Milestones:[/] {', '.join(act['key_milestones'])}")

    tree.add(f"[cyan]Folders Migrated:[/] {', '.join(results['folders_migrated'])} ({results['total_chapters']} total chapters)")
    console.print(Panel(tree, border_style="green", padding=(1, 2)))


def cmd_lore_search(args: argparse.Namespace) -> None:
    from rich.box import ROUNDED
    from rich.table import Table
    from nousetsu.rag.embeddings import EmbeddingClient

    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    engine = repo.get_rag_engine()

    total_docs = engine.count_documents()
    if total_docs == 0:
        console.print(f"[yellow]⚠️ Lore Vault is empty for project at [bold]{repo.root_dir}[/]. Run a batch translation first to index chapters.[/]")
        return

    query = args.query
    limit = getattr(args, "limit", 5) or 5
    folder = getattr(args, "folder", None)
    emb_model = getattr(args, "embedding_model", "text-multilingual-embedding-002")
    rerank_enabled = getattr(args, "rerank", True)
    rerank_model = getattr(args, "reranker_model", "gemini-3.5-flash-lite")

    emb_client = EmbeddingClient(model_name=emb_model)
    query_vec = emb_client.embed_text(query) if emb_client.is_available else None

    from nousetsu.rag.reranker import get_reranker
    reranker = get_reranker(model_name=rerank_model) if rerank_enabled else None

    results = engine.hybrid_search(
        query=query,
        query_vector=query_vec,
        limit=limit,
        folder=folder,
        reranker=reranker,
        enable_rerank=rerank_enabled
    )

    if not results:
        console.print(f"[yellow]No lore entries matched query: '{query}'[/]")
        return

    table = Table(title=f"📚 Lore Vault: '{query}' (Hybrid FTS5 + Gemini Embedding 2 + Cross-Encoder)", box=ROUNDED)
    table.add_column("Rank", justify="center", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Chapter", justify="center", style="bold")
    table.add_column("CE Score", justify="right", style="bold magenta")
    table.add_column("RRF Score", justify="right", style="green")
    table.add_column("Sparse Rank", justify="right")
    table.add_column("Dense Rank", justify="right")
    table.add_column("Snippet", style="white")

    for idx, r in enumerate(results, start=1):
        s_rank_str = f"#{r.sparse_rank}" if r.sparse_rank else "[dim]-[/]"
        d_rank_str = f"#{r.dense_rank}" if r.dense_rank else "[dim]-[/]"
        ce_str = f"{r.rerank_score:.3f}" if r.rerank_score is not None else "[dim]-[/]"
        ch_str = f"Ch.{r.chapter_num}" if r.chapter_num else "-"
        if r.folder:
            ch_str = f"[{r.folder}] {ch_str}"
        snippet = r.content.replace("\n", " ")
        if len(snippet) > 100:
            snippet = snippet[:100] + "..."
        table.add_row(
            str(idx),
            r.doc_type.value,
            ch_str,
            ce_str,
            f"{r.rrf_score:.4f}",
            s_rank_str,
            d_rank_str,
            snippet
        )
    console.print(table)


def cmd_migrate_rag(args: argparse.Namespace) -> None:
    from rich.panel import Panel
    from rich.tree import Tree
    from nousetsu.rag.embeddings import EmbeddingClient
    from nousetsu.rag.migration import migrate_project_to_rag

    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    folder_filter = getattr(args, "folder", None)
    dry_run = getattr(args, "dry_run", False)
    embed = getattr(args, "embed", True)
    batch_size = getattr(args, "batch_size", 50) or 50

    inc_summaries = getattr(args, "include_summaries", True)
    inc_arcs = getattr(args, "include_arcs", True)
    inc_bible = getattr(args, "include_bible", True)
    inc_chunks = getattr(args, "include_chunks", True)

    emb_model = getattr(args, "embedding_model", "text-multilingual-embedding-002")
    embedding_client = EmbeddingClient(model_name=emb_model) if embed else None

    action_label = "[yellow]Dry Run Preview[/]" if dry_run else "[bold green]Migrating Data to RAG (LoreVault)[/]"
    console.print(f"\n{action_label} for project at [bold]{repo.root_dir}[/]...")

    with console.status("[bold cyan]Scanning and indexing lore into SQLite FTS5 / Vector store...[/]", spinner="dots"):
        stats = migrate_project_to_rag(
            repository=repo,
            embedding_client=embedding_client,
            include_summaries=inc_summaries,
            include_arcs=inc_arcs,
            include_bible=inc_bible,
            include_chunks=inc_chunks,
            folder_filter=folder_filter,
            batch_size=batch_size,
            embed=embed,
            dry_run=dry_run
        )

    tree = Tree(f"📚 [bold magenta]RAG Migration Summary[/] ({stats.duration_seconds}s)")
    tree.add(f"[cyan]Folders Scanned:[/] {', '.join(stats.folders_scanned) if stats.folders_scanned else 'all'}")
    tree.add(f"[green]Chapter Summaries:[/] {stats.summaries_indexed}")
    tree.add(f"[green]Story Arcs:[/] {stats.arcs_indexed}")
    tree.add(f"[green]Novel Bible Characters:[/] {stats.characters_indexed}")
    tree.add(f"[green]Glossary Items:[/] {stats.glossary_indexed}")
    tree.add(f"[green]Translated Scene Chunks:[/] {stats.chunks_indexed}")
    tree.add(f"[bold yellow]Total Documents Indexed:[/] {stats.total_indexed}")
    if embed and not dry_run:
        tree.add(f"[bold magenta]Dense Embeddings Generated:[/] {stats.total_embedded}")

    status_note = "[yellow]Dry run complete — no changes written to database.[/]" if dry_run else f"[bold green]✓ Migration successful! Knowledge store ready at {repo.rag_db_path.name}[/]"
    console.print(Panel(tree, subtitle=status_note, border_style="green", padding=(1, 2)))


def cmd_tui(args: argparse.Namespace) -> None:
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    if getattr(args, "source_lang", None) or getattr(args, "target_lang", None):
        repo.set_languages(source_lang=args.source_lang, target_lang=args.target_lang)

    in_dir = getattr(args, "input_dir", None)
    out_dir = getattr(args, "output_dir", None)
    folder_arg = getattr(args, "folder", None)
    if folder_arg:
        raw_cand = repo.root_dir / folder_arg
        if raw_cand.exists() and raw_cand.is_dir():
            in_dir = str(raw_cand)
            if not out_dir:
                out_cand_th = repo.root_dir / f"{folder_arg}_th"
                out_cand_tr = repo.root_dir / f"{folder_arg}_trans"
                out_dir = str(out_cand_th if out_cand_th.exists() else (out_cand_tr if out_cand_tr.exists() else out_cand_th))
            repo.set_active_folder(raw_dir=folder_arg, output_dir=Path(out_dir).name)

    app = NovelAgentApp(
        input_dir=in_dir,
        output_dir=out_dir,
        model_name=getattr(args, "model", None),
        project_dir=project_dir
    )
    app.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Document-Level Novel Translation CLI")
    parser.add_argument("--version", "-v", action="version", version=f"nousetsu {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    default_src = os.environ.get("SOURCE_LANG", "English")
    default_tgt = os.environ.get("TARGET_LANG", "Thai")

    # init
    p_init = subparsers.add_parser("init", help="Initialize novel project and Novel Bible")
    p_init.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_init.add_argument("--title", default="Ascendance of a Bookworm", help="Novel series title")
    p_init.add_argument("--source-lang", default=default_src, help="Source language (e.g. Japanese, Chinese, Korean)")
    p_init.add_argument("--target-lang", default=default_tgt, help="Target language (e.g. English, Spanish)")
    p_init.add_argument("--genre", "-g", default="general", help="Novel genre (e.g. xianxia, wuxia, isekai, litrpg, romance, auto, general)")
    p_init.add_argument("--model", "-m", default=None, help="LLM model override (defaults to .env NOVEL_MODEL)")

    # batch
    p_batch = subparsers.add_parser("batch", help="Run folder-to-folder automated batch translation")
    p_batch.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_batch.add_argument("--folder", "-F", default=None, help="Translation folder within project (auto-resolves matching input/output folders)")
    p_batch.add_argument("--input-dir", "-i", default="raw_chapters", help="Folder containing raw chapters")
    p_batch.add_argument("--output-dir", "-o", default="translated_chapters", help="Folder for translated output")
    p_batch.add_argument("--source-lang", default=None, help="Override source language")
    p_batch.add_argument("--target-lang", default=None, help="Override target language")
    p_batch.add_argument("--genre", "-g", default=None, help="Override novel genre")
    p_batch.add_argument("--model", "-m", default=None, help="Default LLM model override (defaults to project config or .env NOVEL_MODEL)")
    p_batch.add_argument("--fallback-model", default=None, help="Global fallback LLM model name")
    p_batch.add_argument("--extractor-model", default=None, help="Override model for Entity Extractor Agent")
    p_batch.add_argument("--drafter-model", default=None, help="Override model for Drafter Agent")
    p_batch.add_argument("--critic-model", default=None, help="Override model for Critique Agent")
    p_batch.add_argument("--polisher-model", default=None, help="Override model for Polisher Agent")
    p_batch.add_argument("--chronicler-model", default=None, help="Override model for Chronicler Agent")
    p_batch.add_argument("--chapter", "-c", default=None, help="Target a specific chapter number or filename pattern (e.g. --chapter 48)")
    p_batch.add_argument("--limit", "-l", type=int, default=None, help="Maximum number of chapters to process")
    p_batch.add_argument("--force", "-f", action="store_true", help="Force re-translate completed chapters")
    p_batch.add_argument("--auto-update-bible", action=argparse.BooleanOptionalAction, default=None, help="Automatically merge new characters/terms into Novel Bible")
    p_batch.add_argument("--max-tpm", type=int, default=None, help="Max tokens per minute rate limit quota (default: 32000)")
    p_batch.add_argument("--max-rpm", type=int, default=None, help="Max requests per minute rate limit quota (default: 60)")
    p_batch.add_argument("--max-loops", type=int, default=None, help="Maximum review loops for translation refinement (default: 3)")
    p_batch.add_argument("--quality-threshold", type=float, default=None, help="Target quality score threshold (fidelity & style) to exit review loop (default: 8.5)")
    p_batch.add_argument("--interactions", action=argparse.BooleanOptionalAction, default=True, help="Use Gemini Interactions API (/v1beta/interactions) (default: True)")
    p_batch.add_argument("--chunking", action=argparse.BooleanOptionalAction, default=True, help="Enable line-based semantic chunking for long chapters (default: True)")
    p_batch.add_argument("--chunk-threshold-lines", type=int, default=None, help="Line threshold to trigger chunking (default: 85)")
    p_batch.add_argument("--target-chunk-lines", type=int, default=None, help="Target line count per chunk (default: 70)")
    p_batch.add_argument("--rag", action=argparse.BooleanOptionalAction, default=True, help="Enable hybrid search episodic lore retrieval (default: True)")
    p_batch.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=True, help="Enable Stage 2 Cross-Encoder reranking for RAG (default: True)")

    # skills
    p_skills = subparsers.add_parser("skills", help="List registered agent domain skills and active capabilities")
    p_skills.add_argument("--agent", "-a", default=None, help="Filter by agent (extractor, drafter, critic, polisher, chronicler)")
    p_skills.add_argument("--genre", "-g", default=None, help="Filter by genre")
    p_skills.add_argument("--source-lang", "-l", default=None, help="Filter by source language")

    # graph-info
    p_graph = subparsers.add_parser("graph-info", help="Inspect Procedural Graphs with Rich tree formatting (arXiv:2609.09153v1)")
    p_graph.add_argument("--agent", "-a", choices=["all", "extractor", "drafter"], default="all", help="Filter by agent graph (default: all)")

    # narrative
    p_narrative = subparsers.add_parser("narrative", help="Inspect 3-tier hierarchical story memory (Whole Story > Arcs > Situation)")
    p_narrative.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")

    # migrate-summaries
    p_migrate = subparsers.add_parser("migrate-summaries", help="Migrate legacy summaries to 3-tier hierarchical summary system")
    p_migrate.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_migrate.add_argument("--title", default=None, help="Optional novel title override")
    p_migrate.add_argument("--dry-run", action="store_true", help="Preview migration without writing to disk")

    # lore
    p_lore = subparsers.add_parser("lore", help="Search the project Lore Vault using Hybrid RAG + Cross-Encoder")
    p_lore.add_argument("query", help="Text search query (e.g. 'Claire magic sword')")
    p_lore.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_lore.add_argument("--folder", "-F", default=None, help="Filter by specific volume folder")
    p_lore.add_argument("--limit", "-l", type=int, default=5, help="Number of results to display (default: 5)")
    p_lore.add_argument("--embedding-model", default="text-multilingual-embedding-002", help="Embedding model for dense search (default: text-multilingual-embedding-002)")
    p_lore.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=True, help="Enable Cross-Encoder reranking (default: True)")
    p_lore.add_argument("--reranker-model", default="gemini-3.5-flash-lite", help="Cross-Encoder reranker model (default: gemini-3.5-flash-lite)")

    # migrate-rag
    p_mrag = subparsers.add_parser("migrate-rag", aliases=["index-rag"], help="Migrate and backfill novel data (.novel summaries, arcs, bible, chunks) into RAG knowledge store")
    p_mrag.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_mrag.add_argument("--folder", "-F", default=None, help="Restrict migration to a specific volume folder (e.g. Villainess_05)")
    p_mrag.add_argument("--embed", action=argparse.BooleanOptionalAction, default=True, help="Compute dense vector embeddings with EmbeddingClient (default: True if key available)")
    p_mrag.add_argument("--embedding-model", default="text-multilingual-embedding-002", help="Dense embedding model override")
    p_mrag.add_argument("--batch-size", type=int, default=50, help="Batch size for database upserts and embeddings (default: 50)")
    p_mrag.add_argument("--include-summaries", action=argparse.BooleanOptionalAction, default=True, help="Index chapter summaries (default: True)")
    p_mrag.add_argument("--include-arcs", action=argparse.BooleanOptionalAction, default=True, help="Index story arcs (default: True)")
    p_mrag.add_argument("--include-bible", action=argparse.BooleanOptionalAction, default=True, help="Index characters and glossary items (default: True)")
    p_mrag.add_argument("--include-chunks", action=argparse.BooleanOptionalAction, default=True, help="Index translated scene chunks (default: True)")
    p_mrag.add_argument("--dry-run", action="store_true", help="Preview document counts without modifying database")

    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Textual TUI dashboard")
    p_tui.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_tui.add_argument("--folder", "-F", default=None, help="Translation folder within project (auto-resolves matching input/output folders)")
    p_tui.add_argument("--input-dir", "-i", default=None, help="Folder containing raw chapters")
    p_tui.add_argument("--output-dir", "-o", default=None, help="Folder for translated output")
    p_tui.add_argument("--source-lang", default=None, help="Override source language")
    p_tui.add_argument("--target-lang", default=None, help="Override target language")
    p_tui.add_argument("--model", "-m", default=None, help="LLM model override (defaults to project config or .env NOVEL_MODEL)")
    p_tui.add_argument("--fallback-model", default=None, help="Global fallback LLM model name")
    p_tui.add_argument("--interactions", action=argparse.BooleanOptionalAction, default=True, help="Use Gemini Interactions API (/v1beta/interactions) (default: True)")
    p_tui.add_argument("--chunking", action=argparse.BooleanOptionalAction, default=True, help="Enable line-based semantic chunking for long chapters (default: True)")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "skills":
        cmd_skills(args)
    elif args.command == "graph-info":
        cmd_graph_info(args)
    elif args.command == "narrative":
        cmd_narrative(args)
    elif args.command == "migrate-summaries":
        cmd_migrate_summaries(args)
    elif args.command == "lore":
        cmd_lore_search(args)
    elif args.command in ("migrate-rag", "index-rag"):
        cmd_migrate_rag(args)
    elif args.command == "tui":
        cmd_tui(args)
    else:
        # Default behavior when no subcommand is provided: automatically launch TUI dashboard
        reg = ProjectRegistry()
        last_proj = reg.get_last_active_project()
        proj_dir = str(last_proj) if last_proj else "."
        cmd_tui(argparse.Namespace(
            project_dir=proj_dir,
            input_dir=None,
            output_dir=None,
            model=getattr(args, "model", None),
            source_lang=None,
            target_lang=None
        ))


if __name__ == "__main__":
    main()
