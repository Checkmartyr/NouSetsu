"""CLI entry point for Novel Translation Agent."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
import dotenv
from nousetsu import __version__
from nousetsu.batch.runner import BatchRunner
from nousetsu.storage.repository import (
    NovelRepository,
    ProjectRegistry,
    get_projects_root_dir,
    resolve_project_dir,
    get_new_project_dir,
)
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
    target_path = resolve_project_dir(project_dir, for_creation=True, title=args.title)
    repo = NovelRepository(target_path)
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
    repo = NovelRepository(resolve_project_dir(project_dir))
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
        filter_extractor_entities=getattr(args, "filter_extractor", None),
        enable_post_polish_reconciliation=getattr(args, "reconcile_terms", None),
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


def cmd_scan(args: argparse.Namespace) -> None:
    """Scan and display chapter tasks and statistics for projects in NOVEL_PROJECTS_DIR or local."""
    from rich.table import Table
    from nousetsu.batch.scanner import ChapterScanner
    from nousetsu.storage.repository import get_projects_root_dir

    all_projects = getattr(args, "all_projects", False)
    folder = getattr(args, "folder", None)

    if all_projects:
        projects_root = get_projects_root_dir()
        all_tasks_by_proj = ChapterScanner.scan_all_projects(projects_root, folder=folder)

        if not all_tasks_by_proj:
            console.print(f"[yellow]No novel projects discovered inside projects root: {projects_root}[/]")
            return

        table = Table(title=f"Novel Projects Overview ({projects_root.name}/)", border_style="cyan")
        table.add_column("Project", style="bold green")
        table.add_column("Total Ch", justify="right", style="bold")
        table.add_column("Done", justify="right", style="green")
        table.add_column("Paused", justify="right", style="yellow")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Pending", justify="right", style="dim")

        for p_name, tasks in sorted(all_tasks_by_proj.items()):
            done = sum(1 for t in tasks if t.is_completed)
            paused = sum(1 for t in tasks if t.is_paused or t.needs_resume)
            failed = sum(1 for t in tasks if t.is_failed)
            pending = sum(1 for t in tasks if not t.is_completed and not t.is_paused and not t.needs_resume and not t.is_failed)
            table.add_row(
                p_name,
                str(len(tasks)),
                str(done),
                str(paused),
                str(failed),
                str(pending),
            )

        console.print(table)
        return

    project_dir = getattr(args, "project_dir", None)
    scanner = ChapterScanner(project_dir)
    cfg = scanner.repo.load_config()
    tasks = scanner.scan_project(folder=folder)

    if not tasks:
        console.print(f"[yellow]No chapter files found in project '{cfg.title}' ({scanner.repo.root_dir.name}).[/]")
        return

    table = Table(
        title=f"Chapter Queue: {cfg.title} [{scanner.repo.root_dir.name}] ({len(tasks)} chapters)",
        border_style="cyan"
    )
    table.add_column("Ch #", justify="right", style="bold cyan", width=6)
    table.add_column("File Name", style="white")
    table.add_column("Volume / Folder", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Output File", style="dim")

    for t in tasks:
        if t.is_completed:
            status_style = "[green]COMPLETED[/]"
        elif t.is_failed:
            status_style = "[red]FAILED[/]"
        elif t.is_paused or t.needs_resume:
            stage_txt = f":{t.resume_stage.value.upper()}" if t.resume_stage else ""
            status_style = f"[yellow]PAUSED{stage_txt}[/]"
        else:
            status_style = "[dim]PENDING[/]"

        table.add_row(
            str(t.chapter_num),
            t.source_file.name,
            t.folder or "raw_chapters",
            status_style,
            t.output_file.name if t.output_file.exists() else "-"
        )

    console.print(table)
    done_count = sum(1 for t in tasks if t.is_completed)
    paused_count = sum(1 for t in tasks if t.is_paused or t.needs_resume)
    console.print(
        f"[dim]Summary:[/] [green]{done_count} completed[/], "
        f"[yellow]{paused_count} paused[/], "
        f"{len(tasks) - done_count - paused_count} pending.\n"
    )


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
    from nousetsu.graph.procedural import (
        get_default_chronicler_graph,
        get_default_critic_graph,
        get_default_drafter_graph,
        get_default_extractor_graph,
        get_default_polisher_graph,
    )

    project_dir = getattr(args, "project_dir", None)
    folder = getattr(args, "folder", None)
    if folder and not project_dir:
        candidate_p = Path(folder)
        if (candidate_p / ".novel").exists() or (candidate_p / "config.yaml").exists():
            project_dir = str(candidate_p)
            folder = None

    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    agent_filter = (getattr(args, "agent", None) or "all").lower()

    graphs_to_show = []
    if agent_filter in ["all", "extractor"]:
        g = repo.load_procedural_graph("extractor", folder=folder) or get_default_extractor_graph()
        graphs_to_show.append(("Entity Extractor", g))
    if agent_filter in ["all", "drafter"]:
        g = repo.load_procedural_graph("drafter", folder=folder) or get_default_drafter_graph()
        graphs_to_show.append(("Context-Aware Drafter", g))
    if agent_filter in ["all", "critic"]:
        g = repo.load_procedural_graph("critic", folder=folder) or get_default_critic_graph()
        graphs_to_show.append(("Critique Agent", g))
    if agent_filter in ["all", "polisher"]:
        g = repo.load_procedural_graph("polisher", folder=folder) or get_default_polisher_graph()
        graphs_to_show.append(("Polishing Agent", g))
    if agent_filter in ["all", "chronicler"]:
        g = repo.load_procedural_graph("chronicler", folder=folder) or get_default_chronicler_graph()
        graphs_to_show.append(("Chronicler Agent", g))

    if not graphs_to_show:
        console.print(f"[yellow]No procedural graph found for agent '{args.agent}'. Use 'extractor', 'drafter', 'critic', 'polisher', 'chronicler', or 'all'.[/]")
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

        console.print(Panel(tree, border_style="cyan", padding=(1, 2)))


def cmd_learn_graph(args: argparse.Namespace) -> None:
    """Execute offline self-evolution loop for Procedural Graphs (arXiv:2609.09153v1)."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from nousetsu.graph.pg_refiner import ProceduralGraphRefiner, collect_traces_from_repository
    from nousetsu.graph.procedural import (
        get_default_chronicler_graph,
        get_default_critic_graph,
        get_default_drafter_graph,
        get_default_extractor_graph,
        get_default_polisher_graph,
    )

    project_dir = getattr(args, "project_dir", None)
    folder = getattr(args, "folder", None)
    if folder and not project_dir:
        candidate_p = Path(folder)
        if (candidate_p / ".novel").exists() or (candidate_p / "config.yaml").exists():
            project_dir = str(candidate_p)
            folder = None

    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    agent_target = (getattr(args, "agent", None) or "all").lower()
    max_traces = getattr(args, "max_traces", 20) or 20
    dry_run = getattr(args, "dry_run", False)
    model_name = getattr(args, "model", None) or os.environ.get("NOVEL_FALLBACK_MODEL") or "gemini-3.5-flash-lite"

    mode_label = "[yellow]Dry Run Preview[/]" if dry_run else "[bold green]Offline Graph Self-Evolution[/]"
    console.print(f"\n{mode_label} for project at [bold]{repo.root_dir}[/] (Model: [cyan]{model_name}[/])...\n")

    # 1. Collect diagnostic traces
    with console.status("[bold cyan]Scanning project metadata and diagnostic traces...[/]", spinner="dots"):
        traces = collect_traces_from_repository(
            repo=repo,
            folder=folder,
            stage=agent_target,
            max_traces=max_traces
        )

    if not traces:
        console.print("[yellow]No diagnostic traces found in this project yet.[/]")
        console.print("[dim]Translate chapters with CritiqueAgent auditing to generate historical traces for self-evolution.[/]")
        return

    successes = [t for t in traces if t.is_success]
    failures = [t for t in traces if not t.is_success]

    # Render summary table of collected traces
    summary_table = Table(title="Diagnostic Rollout Traces Summary", header_style="bold magenta", border_style="dim")
    summary_table.add_column("Category", style="cyan")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Notes", style="dim")
    summary_table.add_row("Total Traces Analyzed", str(len(traces)), f"Max cap: {max_traces}")
    summary_table.add_row("Clean Success Traces", str(len(successes)), "Fidelity >= 8.5 & 0 warnings")
    summary_table.add_row("Failure / Warning Traces", str(len(failures)), "Critique warnings, tone issues, omissions")
    console.print(summary_table)

    if not failures:
        console.print("\n[bold green]All collected traces have passing quality audits and zero warnings![/]")
        console.print("[cyan]Current procedural execution structures are performing optimally. No mutations required.[/]")
        return

    # 2. Target agents
    agents_to_evolve = []
    if agent_target in ["all", "extractor"]:
        extractor_traces = [t for t in traces if t.stage == "extractor"]
        if extractor_traces:
            current_g = repo.load_procedural_graph("extractor", folder=folder) or get_default_extractor_graph()
            agents_to_evolve.append(("extractor", "Entity Extractor", extractor_traces, current_g))
    if agent_target in ["all", "drafter"]:
        drafter_traces = [t for t in traces if t.stage == "drafter"]
        if drafter_traces:
            current_g = repo.load_procedural_graph("drafter", folder=folder) or get_default_drafter_graph()
            agents_to_evolve.append(("drafter", "Context-Aware Drafter", drafter_traces, current_g))
    if agent_target in ["all", "critic"]:
        critic_traces = [t for t in traces if t.stage == "critic"]
        if critic_traces:
            current_g = repo.load_procedural_graph("critic", folder=folder) or get_default_critic_graph()
            agents_to_evolve.append(("critic", "Critique Agent", critic_traces, current_g))
    if agent_target in ["all", "polisher"]:
        polisher_traces = [t for t in traces if t.stage == "polisher"]
        if polisher_traces:
            current_g = repo.load_procedural_graph("polisher", folder=folder) or get_default_polisher_graph()
            agents_to_evolve.append(("polisher", "Polishing Agent", polisher_traces, current_g))
    if agent_target in ["all", "chronicler"]:
        chronicler_traces = [t for t in traces if t.stage == "chronicler"]
        if chronicler_traces:
            current_g = repo.load_procedural_graph("chronicler", folder=folder) or get_default_chronicler_graph()
            agents_to_evolve.append(("chronicler", "Chronicler Agent", chronicler_traces, current_g))

    if not agents_to_evolve:
        console.print(f"[yellow]No failure traces matched target agent '{agent_target}'.[/]")
        return

    rejection_path = repo.novel_dir / "rejection_memory.json"
    refiner = ProceduralGraphRefiner(model_name=model_name, rejection_memory_path=rejection_path)

    for agent_key, agent_title, stage_traces, current_graph in agents_to_evolve:
        console.print(f"\n[bold cyan]Evolving Procedural Graph for {agent_title} ({current_graph.graph_id})...[/]")

        with console.status(f"[bold green]Synthesizing mutations from {len(stage_traces)} trace(s)...[/]", spinner="dots"):
            evolved_graph, edits = refiner.refine(current_graph, stage_traces)

        if not edits:
            console.print(f"[dim yellow]No mutations committed for {agent_title} (graph remains optimal or candidate failed validation).[/]")
            continue

        tree = Tree(f"[bold green]Committed {len(edits)} Mutation(s) for {agent_title}[/]")
        for edit in edits:
            op_color = "green" if edit.operation == "ADD" else ("yellow" if edit.operation == "UPDATE" else "red")
            leaf = tree.add(f"[{op_color} bold]{edit.operation}[/] [bold]{edit.edge_source} -> {edit.edge_target}[/]")
            if edit.rationale:
                leaf.add(f"[cyan]Rationale:[/] {edit.rationale}")
            if edit.new_guidance:
                leaf.add(f"[white]Guidance:[/] {edit.new_guidance}")
            if edit.new_pitfalls:
                leaf.add(f"[red bold]Pitfalls to Avoid:[/] {edit.new_pitfalls}")

        if dry_run:
            console.print(Panel(tree, subtitle="[yellow]Dry Run: No changes written to disk[/]", border_style="yellow", padding=(1, 2)))
        else:
            saved_path = repo.save_procedural_graph(evolved_graph, agent_key, folder=folder)
            console.print(Panel(tree, subtitle=f"[bold green]✓ Evolved graph saved to {saved_path.name}[/]", border_style="green", padding=(1, 2)))


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


def cmd_realign_chapters(args: argparse.Namespace) -> None:
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    folder = getattr(args, "folder", None)
    if not folder:
        console.print("[red]Error:[/] You must specify --folder (e.g. --folder Villainess_06)")
        return

    dry_run = getattr(args, "dry_run", False)
    re_chronicle = getattr(args, "re_chronicle", False)

    action_label = "[yellow]Dry Run Preview[/]" if dry_run else "[bold green]Realigning Chapters & Fixing Collisions[/]"
    console.print(f"\n{action_label} for folder [bold]{folder}[/] at [bold]{repo.root_dir}[/]...")

    from nousetsu.storage.repair import realign_project_folder
    try:
        report = realign_project_folder(
            repository=repo,
            folder=folder,
            dry_run=dry_run,
            re_chronicle=re_chronicle,
        )
    except Exception as e:
        console.print(f"[bold red]Realignment failed:[/] {e}")
        return

    tree = Tree(f"🔄 [bold magenta]Chapter Alignment Report: {folder}[/] ({report.total_chapters} Total Chapters)")
    if report.backup_path:
        tree.add(f"[cyan]Backup Created:[/] {report.backup_path}")

    if report.realigned_chapters:
        ch_node = tree.add(f"[yellow]Chapters Realigned ({len(report.realigned_chapters)}):[/]")
        for fname, old_ch, new_ch in report.realigned_chapters:
            ch_node.add(f"[white]{fname}[/] : [red]Ch.{old_ch}[/] ➔ [bold green]Ch.{new_ch}[/]")
    else:
        tree.add("[green]✓ No chapter collisions detected — numbering is consistent![/]")

    if report.summaries_moved:
        sum_node = tree.add(f"[blue]Summaries Relocated ({len(report.summaries_moved)}):[/]")
        for old_f, new_f in report.summaries_moved:
            sum_node.add(f"{old_f} ➔ [bold green]{new_f}[/]")

    if report.summaries_reconstructed:
        tree.add(f"[bold cyan]Summaries Reconstructed:[/] {len(report.summaries_reconstructed)} chapters ({', '.join(map(str, report.summaries_reconstructed))})")

    if report.metadata_entries_updated:
        tree.add(f"[green]Metadata Entries Updated:[/] {report.metadata_entries_updated}")

    if report.rag_reindexed:
        tree.add("[bold green]✓ RAG Knowledge Store re-indexed successfully[/]")

    status_note = "[yellow]Dry run preview complete — no changes written to disk.[/]" if dry_run else "[bold green]✓ Chapter realignment completed successfully![/]"
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


def cmd_traces(args: argparse.Namespace) -> None:
    """Inspect, analyze, and export LLM prompt and output traces."""
    project_dir = getattr(args, "project_dir", None)
    repo = NovelRepository(project_dir) if project_dir else NovelRepository()
    folder_arg = getattr(args, "folder", None)
    chapter_arg = getattr(args, "chapter", None)

    if chapter_arg is None:
        # List all available traces
        trace_files = repo.list_chapter_traces(folder=folder_arg)
        if not trace_files:
            # Also check for .jsonl streaming files
            if repo.traces_dir.exists():
                search_dir = repo.traces_dir / folder_arg if folder_arg else repo.traces_dir
                if search_dir.exists():
                    trace_files = sorted(search_dir.rglob("chapter_*.jsonl"))

        if not trace_files:
            console.print(Panel(
                f"[yellow]No agent prompt traces found in [cyan]{repo.traces_dir}[/].[/]\n"
                "Traces will be recorded automatically when running batch translations nya~!",
                title="Prompt & Output Traces",
                border_style="yellow"
            ))
            return

        table = Table(title="🐾 Agent Prompt & Output Traces", border_style="cyan", show_header=True)
        table.add_column("Folder", style="magenta")
        table.add_column("File", style="cyan")
        table.add_column("Chapter", justify="right", style="yellow")
        table.add_column("Format", style="green")
        table.add_column("Size", justify="right")
        table.add_column("Interactions", justify="right")

        for tf in trace_files:
            rel_folder = tf.parent.name if tf.parent != repo.traces_dir else "-"
            m = re.search(r"chapter_(\d+)", tf.stem)
            chap_num_str = m.group(1) if m else "?"
            fmt = "Consolidated JSON" if tf.suffix == ".json" else "Streaming JSONL"
            size_kb = f"{tf.stat().st_size / 1024:.1f} KB"

            interactions_str = "-"
            if tf.suffix == ".json":
                try:
                    with open(tf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        interactions_str = str(data.get("total_interactions", len(data.get("traces", []))))
                except Exception:
                    pass
            elif tf.suffix == ".jsonl":
                try:
                    with open(tf, "r", encoding="utf-8") as f:
                        interactions_str = str(sum(1 for _ in f))
                except Exception:
                    pass

            table.add_row(rel_folder, tf.name, chap_num_str, fmt, size_kb, interactions_str)

        console.print(table)
        console.print("\n[dim]Tip: Use [bold]nousetsu traces --chapter <NUM>[/] to inspect detailed prompts and outputs for a specific chapter nya~![/]\n")
        return

    # Parse chapter number
    try:
        chap_cleaned = str(chapter_arg).lower().replace("chapter_", "").replace("chapter", "").strip()
        chap_num = int(chap_cleaned)
    except ValueError:
        console.print(f"[bold red]Invalid chapter number:[/] {chapter_arg}")
        return

    doc = repo.load_chapter_traces(chapter_num=chap_num, folder=folder_arg)
    if not doc:
        console.print(f"[bold red]No traces found for Chapter {chap_num}[/] (folder: {folder_arg or 'root'}).")
        return

    traces = doc.traces
    if getattr(args, "agent", None):
        agent_filter = args.agent.strip().lower()
        traces = [t for t in traces if t.agent.lower() == agent_filter]
    if getattr(args, "stage", None):
        stage_filter = args.stage.strip().lower()
        traces = [t for t in traces if (t.stage.value if hasattr(t.stage, "value") else str(t.stage)).lower() == stage_filter]

    if getattr(args, "export", None):
        export_path = Path(args.export)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as ef:
            json.dump([t.model_dump() for t in traces], ef, indent=2, ensure_ascii=False)
        console.print(f"[bold green]Successfully exported {len(traces)} traces to [cyan]{export_path}[/]![/]")
        return

    # Render summary table
    summary_table = Table(
        title=f"📜 Chapter {chap_num} Trace Log ({len(traces)} Interactions)",
        border_style="magenta",
        show_header=True
    )
    summary_table.add_column("#", justify="right", style="dim")
    summary_table.add_column("Stage", style="cyan")
    summary_table.add_column("Agent", style="bold yellow")
    summary_table.add_column("Model", style="blue")
    summary_table.add_column("Status", justify="center")
    summary_table.add_column("Tokens (In/Out)", justify="right")
    summary_table.add_column("Time", justify="right")
    summary_table.add_column("Output Preview", style="italic")

    for idx, tr in enumerate(traces, 1):
        status_style = "green" if tr.status == "success" else ("yellow" if tr.status == "safety_blocked" else "red")
        status_text = f"[{status_style}]{tr.status}[/]"
        tok_str = f"{tr.token_usage.input_tokens:,} / {tr.token_usage.output_tokens:,}"
        time_str = f"{tr.duration_seconds:.2f}s"
        preview = (tr.raw_output or "").replace("\n", " ").strip()[:60]
        if tr.parsed_output and isinstance(tr.parsed_output, dict):
            preview = json.dumps(tr.parsed_output)[:60]
        if tr.error_message:
            preview = f"[red]{tr.error_message[:60]}[/]"

        summary_table.add_row(
            str(idx),
            tr.stage.value if hasattr(tr.stage, "value") else str(tr.stage),
            tr.agent,
            tr.model,
            status_text,
            tok_str,
            time_str,
            preview
        )

    console.print(summary_table)

    show_prompts = getattr(args, "show_prompts", False)
    show_outputs = getattr(args, "show_outputs", False)

    if show_prompts or show_outputs:
        for idx, tr in enumerate(traces, 1):
            st_val = tr.stage.value if hasattr(tr.stage, "value") else str(tr.stage)
            header = f"Interaction #{idx}: [{tr.agent.upper()}] - {st_val} ({tr.model}) - {tr.duration_seconds:.2f}s"
            console.print(Panel(
                f"[bold cyan]Timestamp:[/] {tr.timestamp} | [bold cyan]Status:[/] {tr.status} | [bold cyan]Tokens:[/] In={tr.token_usage.input_tokens}, Out={tr.token_usage.output_tokens}",
                title=header,
                border_style="cyan"
            ))

            if show_prompts:
                console.print(Panel(
                    Syntax(tr.system_prompt, "markdown", word_wrap=True) if tr.system_prompt else Markdown("_None_"),
                    title=f"🛠️ System Prompt (#{idx})",
                    border_style="dim blue"
                ))
                console.print(Panel(
                    Syntax(tr.user_prompt, "markdown", word_wrap=True) if tr.user_prompt else Markdown("_None_"),
                    title=f"👤 User Prompt (#{idx})",
                    border_style="blue"
                ))

            if show_outputs:
                out_content = tr.raw_output or tr.error_message or "No output."
                console.print(Panel(
                    Syntax(out_content, "markdown", word_wrap=True),
                    title=f"✨ Output (#{idx})",
                    border_style="green" if tr.status == "success" else "red"
                ))
    else:
        console.print("[dim]Tip: Add [bold]--show-prompts[/] or [bold]--show-outputs[/] to inspect full prompt and completion texts.[/]\n")


def cmd_web(args: argparse.Namespace) -> None:
    """Launch the Nousetsu Vite Trace Visualizer web app."""
    import subprocess
    import threading
    import webbrowser
    from nousetsu.cli.web_server import NousetsuWebHandler, run_web_server

    port = getattr(args, "port", 5173) or 5173
    dev_mode = getattr(args, "dev", False)
    do_build = getattr(args, "build", False)
    project_dir = getattr(args, "project_dir", None)
    folder = getattr(args, "folder", None)

    # Locate web/ directory relative to codebase root or repo
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    web_dir = repo_root / "web"
    if not web_dir.exists():
        repo = NovelRepository(project_dir=project_dir)
        web_dir = repo.root_dir / "web"

    if not web_dir.exists():
        console.print(f"[bold red]Web frontend directory not found at:[/] {web_dir}")
        return

    dist_dir = web_dir / "dist"

    if do_build or (not dev_mode and not dist_dir.exists()):
        console.print("[cyan]Building frontend assets with npm run build...[/]")
        try:
            subprocess.run(["npm", "run", "build"], cwd=str(web_dir), check=True, shell=(sys.platform == "win32"))
        except Exception as e:
            console.print(f"[bold yellow]Build warning or error:[/] {e}")

    url = f"http://localhost:{port}"
    reg = ProjectRegistry()
    if project_dir:
        p_path = resolve_project_dir(project_dir)
        if p_path.exists():
            reg.register_project(p_path)
            reg.set_last_active_project(p_path)
    active_p = reg.get_last_active_project() or resolve_project_dir(None)

    if dev_mode or not dist_dir.exists():
        # Start API server on 5174 in background thread for Vite proxy
        api_port = 5174
        t = threading.Thread(
            target=run_web_server,
            kwargs={"port": api_port, "host": "127.0.0.1", "open_browser": False, "dist_dir": dist_dir},
            daemon=True
        )
        t.start()
        console.print(f"[bold green]Starting Vite dev server on[/] [cyan]{url}[/] (API backend on :{api_port}) nya~!")
        console.print(f"[dim]Active TUI Project: {active_p}[/]")
        webbrowser.open(url)
        try:
            subprocess.run(["npm", "run", "dev", "--", "--port", str(port)], cwd=str(web_dir), shell=(sys.platform == "win32"))
        except KeyboardInterrupt:
            console.print("\n[yellow]Dev server stopped.[/]")
    else:
        console.print(Panel.fit(
            f"[bold green]🐾 Nousetsu Trace Visualizer Running![/]\n\n"
            f"URL: [link={url}][cyan]{url}[/link][/]\n"
            f"Active TUI Project: [bold cyan]{active_p.name}[/] ([dim]{active_p}[/])\n"
            f"Serving: [dim]{dist_dir}[/]\n\n"
            f"[magenta]Press Ctrl+C to stop the server (=^･ω･^=)[/]",
            title="Web Visualizer Active",
            border_style="cyan"
        ))
        run_web_server(port=port, host="127.0.0.1", open_browser=True, dist_dir=dist_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Document-Level Novel Translation CLI")
    parser.add_argument("--version", "-v", action="version", version=f"nousetsu {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    default_src = os.environ.get("SOURCE_LANG", "English")
    default_tgt = os.environ.get("TARGET_LANG", "Thai")

    # init
    p_init = subparsers.add_parser("init", help="Initialize novel project and Novel Bible")
    p_init.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project (defaults to NOVEL_PROJECTS_DIR/<title>, e.g. project/<title>)")
    p_init.add_argument("--title", default="Ascendance of a Bookworm", help="Novel series title")
    p_init.add_argument("--source-lang", default=default_src, help="Source language (e.g. Japanese, Chinese, Korean)")
    p_init.add_argument("--target-lang", default=default_tgt, help="Target language (e.g. English, Spanish)")
    p_init.add_argument("--genre", "-g", default="general", help="Novel genre (e.g. xianxia, wuxia, isekai, litrpg, romance, auto, general)")
    p_init.add_argument("--model", "-m", default=None, help="LLM model override (defaults to .env NOVEL_MODEL)")

    # batch
    p_batch = subparsers.add_parser("batch", help="Run folder-to-folder automated batch translation")
    p_batch.add_argument("--project-dir", "-p", default=None, help="Folder or name of novel project (resolves in NOVEL_PROJECTS_DIR or current directory)")
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
    p_batch.add_argument("--filter-extractor", action=argparse.BooleanOptionalAction, default=None, help="Enable or disable per-chunk character/glossary filtering for Entity Extractor")
    p_batch.add_argument("--reconcile-terms", action=argparse.BooleanOptionalAction, default=None, help="Enable post-polish term and character reconciliation via Chronicler Agent (default: True)")

    # scan
    p_scan = subparsers.add_parser("scan", help="Fast scan chapter queue and project status in NOVEL_PROJECTS_DIR")
    p_scan.add_argument("--project-dir", "-p", default=None, help="Folder or name of novel project (resolves in NOVEL_PROJECTS_DIR or current directory)")
    p_scan.add_argument("--folder", "-F", default=None, help="Specific volume folder to scan")
    p_scan.add_argument("--all-projects", "-A", action="store_true", help="Scan across all projects in NOVEL_PROJECTS_DIR")

    # skills
    p_skills = subparsers.add_parser("skills", help="List registered agent domain skills and active capabilities")
    p_skills.add_argument("--agent", "-a", default=None, help="Filter by agent (extractor, drafter, critic, polisher, chronicler)")
    p_skills.add_argument("--genre", "-g", default=None, help="Filter by genre")
    p_skills.add_argument("--source-lang", "-l", default=None, help="Filter by source language")

    # graph-info
    p_graph = subparsers.add_parser("graph-info", help="Inspect Procedural Graphs with Rich tree formatting (arXiv:2609.09153v1)")
    p_graph.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_graph.add_argument("--folder", "-F", default=None, help="Filter by specific volume folder")
    p_graph.add_argument("--agent", "-a", choices=["all", "extractor", "drafter", "critic", "polisher", "chronicler"], default="all", help="Filter by agent graph (default: all)")

    # learn-graph / refine-graph
    p_learn = subparsers.add_parser("learn-graph", aliases=["refine-graph"], help="Execute offline self-evolution loop for Procedural Graphs (arXiv:2609.09153v1)")
    p_learn.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_learn.add_argument("--folder", "-F", default=None, help="Filter by specific volume folder")
    p_learn.add_argument("--agent", "-a", choices=["all", "extractor", "drafter", "critic", "polisher", "chronicler"], default="all", help="Target agent graph to evolve (default: all)")
    p_learn.add_argument("--model", "-m", default=None, help="LLM model for refiner (defaults to NOVEL_FALLBACK_MODEL or gemini-3.5-flash-lite)")
    p_learn.add_argument("--max-traces", type=int, default=20, help="Maximum number of historical traces to analyze (default: 20)")
    p_learn.add_argument("--dry-run", action="store_true", help="Preview proposed mutations without persisting to disk")

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

    # traces
    p_traces = subparsers.add_parser("traces", help="Inspect, analyze, and export agent prompt and output traces")
    p_traces.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_traces.add_argument("--folder", "-F", default=None, help="Filter by specific volume folder")
    p_traces.add_argument("--chapter", "-c", default=None, help="Chapter number to inspect (e.g. 1 or 48)")
    p_traces.add_argument("--agent", "-a", choices=["extractor", "drafter", "critic", "polisher", "chronicler"], default=None, help="Filter by specific agent")
    p_traces.add_argument("--stage", "-s", choices=["extraction", "drafting", "critique", "polishing", "chronicling"], default=None, help="Filter by pipeline stage")
    p_traces.add_argument("--show-prompts", action="store_true", help="Display full system and user input prompts")
    p_traces.add_argument("--show-outputs", action="store_true", help="Display full raw agent outputs")
    p_traces.add_argument("--export", default=None, help="Export filtered traces to specified JSON file")

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

    # web
    p_web = subparsers.add_parser("web", help="Launch interactive Trace Visualizer web app in your browser")
    p_web.add_argument("--project-dir", "-P", default=None, help="Folder or name of novel project (resolves in NOVEL_PROJECTS_DIR or current directory)")
    p_web.add_argument("--folder", "-F", default=None, help="Specific volume folder to focus on")
    p_web.add_argument("--port", "-p", type=int, default=5173, help="Port to run visualizer server on (default: 5173)")
    p_web.add_argument("--dev", action="store_true", help="Run with live Vite dev server instead of production dist")
    p_web.add_argument("--build", action="store_true", help="Rebuild frontend assets before launching")

    # realign-chapters
    p_realign = subparsers.add_parser("realign-chapters", aliases=["realign"], help="Detect and resolve chapter numbering collisions, relocate summaries/traces, and re-index RAG")
    p_realign.add_argument("--project-dir", "-p", default=None, help="Root folder of novel project")
    p_realign.add_argument("--folder", "-F", required=True, help="Volume folder to realign (e.g. Villainess_06)")
    p_realign.add_argument("--dry-run", action="store_true", help="Preview realignment changes without modifying disk")
    p_realign.add_argument("--re-chronicle", action="store_true", help="Use ChroniclerAgent to re-generate summaries for vacated chapter slots")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "traces":
        cmd_traces(args)
    elif args.command == "web":
        cmd_web(args)
    elif args.command == "skills":
        cmd_skills(args)
    elif args.command == "graph-info":
        cmd_graph_info(args)
    elif args.command in ("learn-graph", "refine-graph"):
        cmd_learn_graph(args)
    elif args.command == "narrative":
        cmd_narrative(args)
    elif args.command == "migrate-summaries":
        cmd_migrate_summaries(args)
    elif args.command == "lore":
        cmd_lore_search(args)
    elif args.command in ("migrate-rag", "index-rag"):
        cmd_migrate_rag(args)
    elif args.command in ("realign-chapters", "realign"):
        cmd_realign_chapters(args)
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
