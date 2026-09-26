import time
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich.tree import Tree
from rich.syntax import Syntax
from rich.align import Align

console = Console()

def type_text(text: str, delay: float = 0.03, style: str = "bold white"):
    for ch in text:
        console.print(f"[{style}]{ch}[/]", end="")
        sys.stdout.flush()
        time.sleep(delay)
    console.print()

def main():
    console.clear()
    time.sleep(0.5)

    # 1. Title Banner
    banner_text = """
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║   🐾  N O U S E T S U   •   AI NOVEL TRANSLATION AGENT FRAMEWORK       ║
    ║   Document-Level • LangGraph Reflection Loop • 3-Tier Story Memory       ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(Align.center(banner_text), border_style="cyan", padding=(1, 2)))
    time.sleep(1.2)

    # 2. Scanning Project
    console.print("\n[bold cyan]1. Fast Parallel Project Scanner (NOVEL_PROJECTS_DIR)[/]")
    time.sleep(0.4)

    table = Table(title="Novel Projects Overview (project/)", border_style="bright_blue")
    table.add_column("Project", style="cyan bold")
    table.add_column("Total Ch", justify="right")
    table.add_column("Done", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")
    table.add_column("Source ➔ Target", style="magenta")

    table.add_row("Douyara", "288", "60", "228", "Japanese ➔ Thai")
    table.add_row("Villainess", "224", "221", "3", "Japanese ➔ English")
    table.add_row("Yome Musou", "90", "90", "0", "Japanese ➔ English")
    console.print(table)
    time.sleep(1.5)

    # 3. Running Multi-Agent Pipeline Simulation
    console.print("\n[bold green]2. Executing 5-Stage Agent Pipeline (Chapter 48)[/]")
    stages = [
        ("Stage 1: Entity Extractor", "Extracting unknown characters & cultivation realms...", 0.9),
        ("Stage 2: Context-Aware Drafter", "Resolving zero-anaphora pronouns using Novel Bible...", 1.2),
        ("Stage 3: Critique Agent", "Line-by-line fidelity & glossary compliance audit...", 1.0),
        ("Stage 4: Polishing Agent", "Diff/patch search-replace styling & cadence refinement...", 1.1),
        ("Stage 5: Chronicler Agent", "Updating 3-tier story arcs & indexing to SQLite RAG...", 0.8),
    ]

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        for stage_name, desc, duration in stages:
            task = progress.add_task(f"[bold cyan]{stage_name}[/]: [dim]{desc}[/]", total=100)
            for _ in range(20):
                progress.advance(task, 5)
                time.sleep(duration / 20)
    time.sleep(0.8)

    # 4. Critique Quality Gate
    console.print("\n[bold yellow]3. LangGraph Reflection Review Loop Scorecard[/]")
    audit_table = Table(border_style="green")
    audit_table.add_column("Metric", style="white bold")
    audit_table.add_column("Score", justify="right")
    audit_table.add_column("Threshold", justify="right")
    audit_table.add_column("Status", style="bold")

    audit_table.add_row("Fidelity Score", "[cyan]9.4 / 10[/]", "8.5 / 10", "[green]PASSED ✓[/]")
    audit_table.add_row("Literary Style", "[green]9.2 / 10[/]", "8.5 / 10", "[green]PASSED ✓[/]")
    audit_table.add_row("Zero-Anaphora Check", "[magenta]100%[/]", "95%", "[green]VERIFIED ✓[/]")
    audit_table.add_row("Glossary Enforcement", "[yellow]Strict[/]", "Active", "[green]COMPLIANT ✓[/]")
    console.print(audit_table)
    time.sleep(1.5)

    # 5. 3-Tier Narrative Memory
    console.print("\n[bold magenta]4. 3-Tier Narrative Memory Hierarchy[/]")
    tree = Tree("[bold cyan]Novel Series: Ascendance of a Bookworm[/]")
    macro = tree.add("🌐 [bold yellow]Tier 1 (Macro): Whole Story Summary[/]")
    macro.add("[dim]Myne awakens in Ehrenfest lower city, striving to invent paper and print books.[/]")
    
    meso = tree.add("📖 [bold green]Tier 2 (Meso): Story Arc 02 (The Temple Apprentice)[/]")
    meso.add("[white]Core Conflict: High Bishop intrigue, Devouring mana contract negotiations.[/]")
    meso.add("[dim]Active Status: Ongoing (Ch. 34-60)[/]")

    micro = tree.add("📄 [bold magenta]Tier 3 (Micro): Immediate Chapter Summaries[/]")
    micro.add("Chapter 46: Ferdinand discovers Myne's past memories during sync.")
    micro.add("Chapter 47: Myne crafts high-purity ink with Lutz and Guildmaster.")
    console.print(Panel(tree, border_style="magenta", padding=(1, 2)))
    time.sleep(1.8)

    # 6. Call to Action Outro
    console.print("\n" + "=" * 76)
    type_text("⭐ 100% Open Source on GitHub: https://github.com/Checkmartyr/NouSetsu", delay=0.02, style="bold cyan")
    type_text("🐾 Launch with Docker in 1 command: docker compose up -d", delay=0.02, style="bold green")
    type_text("Happy translating nya~! (=^･ω･^=) ★", delay=0.03, style="bold magenta")
    console.print("=" * 76 + "\n")

if __name__ == "__main__":
    main()
