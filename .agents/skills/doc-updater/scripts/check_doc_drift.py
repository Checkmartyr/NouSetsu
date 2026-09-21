#!/usr/bin/env python3
"""
check_doc_drift.py - Branch-Aware Documentation Drift & Integrity Auditor

Compares the current branch against main to produce an actionable change manifest:
- Generates full branch diff (current branch vs main) and categorizes by subsystem.
- Maps changed files to documentation targets that need updating.
- Scans CLI subcommands/options vs. documented references.
- Counts total tests via pytest collector.
- Validates internal file:// markdown links.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# Subsystem categorization rules: regex pattern on file path -> (category, doc_targets)
SUBSYSTEM_RULES: List[Tuple[str, str, List[str]]] = [
    (r"src/nousetsu/agents/", "Pipeline Agents", ["AGENTS.md (Sec 3)", "doc/agents_deep_dive.md"]),
    (r"src/nousetsu/cli/", "CLI & Commands", ["README.md", "AGENTS.md (Sec 8)", "doc/user_guide.md"]),
    (r"src/nousetsu/graph/", "Workflow & Orchestration", ["AGENTS.md (Sec 2, 4)", "doc/workflow.md"]),
    (r"src/nousetsu/prompts/", "Prompts & Templates", ["AGENTS.md (Sec 3, 5)", "doc/agents_deep_dive.md"]),
    (r"src/nousetsu/skills/", "Agent Skills", ["AGENTS.md (Sec 5)", "README.md"]),
    (r"src/nousetsu/storage/", "Storage & Persistence", ["AGENTS.md (Sec 6)", "doc/storage_and_checkpoints.md"]),
    (r"src/nousetsu/rag/", "Hybrid RAG", ["AGENTS.md (Sec 7.9)", "doc/hybrid_rag.md"]),
    (r"src/nousetsu/tui/", "TUI Interface", ["README.md", "doc/tui_guide.md", "AGENTS.md (Sec 7.14)"]),
    (r"src/nousetsu/utils/", "Utilities & Engines", ["AGENTS.md (Sec 7)", "doc/architecture.md"]),
    (r"src/nousetsu/models/", "Data Models", ["AGENTS.md (Sec 6)", "doc/api_reference.md"]),
    (r"web/", "Web Dashboard", ["README.md", "AGENTS.md (Sec 7.12)"]),
    (r"tests/", "Test Suite", ["README.md", "AGENTS.md (Sec 7.7)"]),
    (r"\.env", "Environment Config", ["README.md", "AGENTS.md (Sec 6)"]),
    (r"AGENTS\.md|README\.md|CHANGELOG\.md", "Documentation", []),
    (r"doc/", "Documentation", []),
    (r"DESIGN\.md", "Design Specs", []),
]


def get_console():
    if HAS_RICH:
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        return Console()
    return None


def find_repo_root(start: Path) -> Path:
    """Walk up from start to find repository root (.git or pyproject.toml)."""
    curr = start.resolve()
    for p in [curr] + list(curr.parents):
        if (p / ".git").is_dir() or (p / "pyproject.toml").is_file():
            return p
    return curr


def run_cmd(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    """Run a shell command safely and return (returncode, stdout)."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)


def get_current_branch(repo_root: Path) -> str:
    """Return the current branch name."""
    code, out = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    return out if code == 0 else "unknown"


def get_main_branch(repo_root: Path) -> str:
    """Detect the main/master branch name."""
    for candidate in ["main", "master"]:
        code, _ = run_cmd(["git", "rev-parse", "--verify", candidate], repo_root)
        if code == 0:
            return candidate
    return "main"


def get_merge_base(repo_root: Path, main_branch: str) -> Optional[str]:
    """Find the merge base between current HEAD and main."""
    code, out = run_cmd(["git", "merge-base", main_branch, "HEAD"], repo_root)
    return out[:12] if code == 0 and out else None


def get_branch_diff_stats(repo_root: Path, main_branch: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Get the branch diff summary and per-file change list.

    Returns:
        (stat_summary, [(status, filepath), ...])
        status: A=added, M=modified, D=deleted, R=renamed
    """
    code, stat_out = run_cmd(["git", "diff", f"{main_branch}...HEAD", "--stat"], repo_root)
    stat_summary = stat_out if code == 0 else ""

    code, name_out = run_cmd(["git", "diff", f"{main_branch}...HEAD", "--name-status"], repo_root)
    changes: List[Tuple[str, str]] = []
    if code == 0 and name_out:
        for line in name_out.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                status, filepath = parts[0][0], parts[1]  # Take first char of status
                changes.append((status, filepath))
            elif len(parts) == 1 and "\t" not in line:
                # Handle rename format: R100\told\tnew
                raw_parts = line.strip().split("\t")
                if len(raw_parts) >= 3:
                    changes.append(("R", raw_parts[2]))  # Use new name
    return stat_summary, changes


def get_branch_commits(repo_root: Path, main_branch: str) -> List[Tuple[str, str]]:
    """Get commits on the current branch not in main."""
    code, out = run_cmd(["git", "log", f"{main_branch}..HEAD", "--oneline"], repo_root)
    if code != 0 or not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) == 2:
            commits.append((parts[0], parts[1]))
        elif len(parts) == 1:
            commits.append((parts[0], ""))
    return commits


def categorize_changes(changes: List[Tuple[str, str]]) -> Dict[str, Dict[str, Any]]:
    """Categorize changed files by subsystem and collect doc targets.

    Returns:
        {category: {"files": [(status, path)], "doc_targets": set()}}
    """
    categories: Dict[str, Dict[str, Any]] = {}
    uncategorized: List[Tuple[str, str]] = []

    for status, filepath in changes:
        matched = False
        for pattern, category, doc_targets in SUBSYSTEM_RULES:
            if re.search(pattern, filepath):
                if category not in categories:
                    categories[category] = {"files": [], "doc_targets": set()}
                categories[category]["files"].append((status, filepath))
                categories[category]["doc_targets"].update(doc_targets)
                matched = True
                break
        if not matched:
            uncategorized.append((status, filepath))

    if uncategorized:
        categories["Other"] = {"files": uncategorized, "doc_targets": set()}

    return categories


def collect_cli_commands(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Parse argparse subcommands and options from nousetsu/cli/app.py."""
    commands: Dict[str, Dict[str, Any]] = {}
    cli_app_file = repo_root / "src" / "nousetsu" / "cli" / "app.py"
    if not cli_app_file.is_file():
        return commands

    content = cli_app_file.read_text(encoding="utf-8", errors="replace")

    parser_re = re.compile(
        r'(\w+)\s*=\s*subparsers\.add_parser\(\s*["\']([^"\']+)["\']'
        r'(?:,\s*aliases=\[([^\]]+)\])?.*?'
        r'help=["\']([^"\']+)["\']',
        re.DOTALL
    )

    for m in parser_re.finditer(content):
        var_name = m.group(1)
        cmd_name = m.group(2)
        aliases_raw = m.group(3) or ""
        help_text = m.group(4)

        aliases = [a.strip().strip("'\"") for a in aliases_raw.split(",") if a.strip()]

        arg_re = re.compile(
            rf'{re.escape(var_name)}\.add_argument\(\s*(["\'][^"\']+["\'](?:,\s*["\'][^"\']+["\'])*)'
        )
        options = []
        for am in arg_re.finditer(content):
            raw_args = am.group(1)
            for opt in re.findall(r'["\'](-{1,2}[a-zA-Z0-9_-]+)["\']', raw_args):
                options.append(opt)

        commands[cmd_name] = {
            "help": help_text,
            "aliases": aliases,
            "options": options,
        }

    return commands


def count_pytest_tests(repo_root: Path) -> Tuple[int, int]:
    """Return (test_count, module_count) using pytest collector."""
    code, out = run_cmd([sys.executable, "-m", "pytest", "--collect-only", "-q"], repo_root)
    if code != 0:
        return 0, 0
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    test_count = 0
    modules: Set[str] = set()
    for line in lines:
        if "::" in line:
            test_count += 1
            mod = line.split("::")[0]
            modules.add(mod)
        elif "collected" in line and "items" in line:
            m = re.search(r"(\d+)\s+(?:test\s+)?items?\s+collected", line)
            if m:
                test_count = int(m.group(1))
    return test_count, len(modules)


def audit_documentation_files(
    repo_root: Path,
    cli_commands: Dict[str, Dict[str, Any]],
    test_count: int
) -> Dict[str, Any]:
    """Scan docs for CLI mentions, test counts, and broken file links."""
    doc_paths = [
        repo_root / "README.md",
        repo_root / "AGENTS.md",
        repo_root / "CHANGELOG.md",
    ]
    doc_dir = repo_root / "doc"
    if doc_dir.is_dir():
        for p in doc_dir.rglob("*.md"):
            doc_paths.append(p)

    results: Dict[str, Any] = {
        "missing_cli_in_docs": {},
        "stale_test_counts": [],
        "broken_links": [],
        "audited_files_count": len(doc_paths),
    }

    all_doc_content: Dict[Path, str] = {}
    aggregated_text = ""
    for path in doc_paths:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                all_doc_content[path] = content
                aggregated_text += f"\n{content}"
            except Exception:
                pass

    # Check CLI commands
    for cmd_name in cli_commands:
        if cmd_name == "_error":
            continue
        pattern = rf"\bnousetsu\s+{re.escape(cmd_name)}\b"
        if not re.search(pattern, aggregated_text):
            results["missing_cli_in_docs"][cmd_name] = cli_commands[cmd_name]["help"]

    # Check test count discrepancies
    for path, content in all_doc_content.items():
        for m in re.finditer(r"(\d{2,4})\s+tests\s+across\s+(\d{1,3})\s+modules", content):
            doc_tests = int(m.group(1))
            doc_mods = int(m.group(2))
            if test_count > 0 and doc_tests != test_count:
                rel_path = path.relative_to(repo_root)
                results["stale_test_counts"].append({
                    "file": str(rel_path),
                    "documented": f"{doc_tests} tests / {doc_mods} modules",
                    "actual": f"{test_count} tests",
                    "match": m.group(0),
                })

    # Check file:// links
    link_pattern = re.compile(r"\[([^\]]+)\]\((file:///[^\)]+)\)")
    for path, content in all_doc_content.items():
        for m in link_pattern.finditer(content):
            target = m.group(2)
            target_clean = target.split("#")[0]
            norm = target_clean.replace("file:///", "").replace("/", os.sep)
            target_path = Path(norm)
            if str(repo_root).lower() in str(target_path).lower() and not target_path.exists():
                results["broken_links"].append({
                    "file": str(path.relative_to(repo_root)),
                    "text": m.group(1),
                    "target": target,
                })

    return results


def main() -> int:
    repo_root = find_repo_root(Path(__file__))
    console = get_console()

    # 1. Branch detection
    current_branch = get_current_branch(repo_root)
    main_branch = get_main_branch(repo_root)
    merge_base = get_merge_base(repo_root, main_branch)
    is_on_main = current_branch in ("main", "master")

    # 2. Branch diff (current vs main)
    if is_on_main:
        # Fallback: compare last 10 commits on main
        stat_summary = ""
        _, name_out = run_cmd(["git", "diff", "--name-status", "HEAD~10", "HEAD"], repo_root)
        changes: List[Tuple[str, str]] = []
        if name_out:
            for line in name_out.splitlines():
                parts = line.strip().split("\t", 1)
                if len(parts) == 2:
                    changes.append((parts[0][0], parts[1]))
        branch_commits = get_branch_commits(repo_root, f"HEAD~10") if not is_on_main else []
    else:
        stat_summary, changes = get_branch_diff_stats(repo_root, main_branch)
        branch_commits = get_branch_commits(repo_root, main_branch)

    # 3. Categorize changes
    categories = categorize_changes(changes)

    # 4. Collect codebase telemetry
    cli_commands = collect_cli_commands(repo_root)
    test_count, module_count = count_pytest_tests(repo_root)
    audit = audit_documentation_files(repo_root, cli_commands, test_count)

    # 5. Collect all doc targets
    all_doc_targets: Set[str] = set()
    for cat_info in categories.values():
        all_doc_targets.update(cat_info["doc_targets"])

    # 6. Render Results
    if HAS_RICH and console:
        # Header
        branch_info = (
            f"Branch: [bold yellow]{current_branch}[/bold yellow] vs "
            f"[bold green]{main_branch}[/bold green]"
        )
        if merge_base:
            branch_info += f"  (merge-base: [dim]{merge_base}[/dim])"

        console.print(Panel.fit(
            f"[bold cyan]Branch-Aware Documentation Drift Report[/bold cyan]\n"
            f"Repository: [green]{repo_root}[/green]\n"
            f"{branch_info}\n"
            f"Changed Files: [bold magenta]{len(changes)}[/bold magenta] | "
            f"Active Tests: [bold magenta]{test_count}[/bold magenta] in "
            f"[magenta]{module_count}[/magenta] modules | "
            f"Audited Docs: [yellow]{audit['audited_files_count']}[/yellow] files",
            box=box.ROUNDED,
            border_style="cyan"
        ))

        # Branch Commits
        if branch_commits:
            commit_table = Table(
                title=f"Branch Commits ({current_branch} ahead of {main_branch})",
                box=box.SIMPLE_HEAVY
            )
            commit_table.add_column("Hash", style="cyan", width=9)
            commit_table.add_column("Message", style="white")
            for h, msg in branch_commits[:15]:
                commit_table.add_row(h, msg)
            if len(branch_commits) > 15:
                commit_table.add_row("...", f"[dim]+{len(branch_commits) - 15} more[/dim]")
            console.print(commit_table)

        # Change Manifest by Subsystem
        if categories:
            console.print()
            manifest_tree = Tree(
                f"[bold cyan]Change Manifest[/bold cyan] "
                f"([bold]{len(changes)}[/bold] files across "
                f"[bold]{len(categories)}[/bold] subsystems)"
            )
            status_icons = {"A": "[green]+[/green]", "M": "[yellow]~[/yellow]",
                            "D": "[red]-[/red]", "R": "[blue]>[/blue]"}

            for category, info in sorted(categories.items()):
                doc_hint = ""
                if info["doc_targets"]:
                    targets = ", ".join(sorted(info["doc_targets"]))
                    doc_hint = f"  [dim]-> {targets}[/dim]"

                cat_branch = manifest_tree.add(
                    f"[bold yellow]{category}[/bold yellow] "
                    f"([bold]{len(info['files'])}[/bold] files){doc_hint}"
                )
                for status, filepath in info["files"]:
                    icon = status_icons.get(status, "[white]?[/white]")
                    cat_branch.add(f"{icon} {filepath}")

            console.print(manifest_tree)

        # Documentation Targets Summary
        if all_doc_targets:
            console.print()
            target_table = Table(
                title="Documentation Files Requiring Updates",
                box=box.SIMPLE_HEAVY
            )
            target_table.add_column("Target Document", style="bold green")
            target_table.add_column("Triggered By", style="white")
            for target in sorted(all_doc_targets):
                triggers = [cat for cat, info in categories.items() if target in info["doc_targets"]]
                target_table.add_row(target, ", ".join(triggers))
            console.print(target_table)

        # CLI Documentation Status
        cli_table = Table(title="CLI Subcommands Documentation Status", box=box.SIMPLE_HEAVY)
        cli_table.add_column("Subcommand", style="bold green")
        cli_table.add_column("Status", style="bold")
        cli_table.add_column("Description", style="white")
        for cmd, info in sorted(cli_commands.items()):
            if cmd == "_error":
                continue
            if cmd in audit["missing_cli_in_docs"]:
                cli_table.add_row(
                    f"nousetsu {cmd}",
                    "[bold red]MISSING IN DOCS[/bold red]",
                    info["help"]
                )
            else:
                cli_table.add_row(
                    f"nousetsu {cmd}",
                    "[bold green]DOCUMENTED[/bold green]",
                    info["help"]
                )
        console.print(cli_table)

        # Stale Test Counts
        if audit["stale_test_counts"]:
            stale_table = Table(title="Stale Test Count References", box=box.SIMPLE_HEAVY)
            stale_table.add_column("Document File", style="yellow")
            stale_table.add_column("Documented Text", style="red")
            stale_table.add_column("Actual Codebase Value", style="green")
            for item in audit["stale_test_counts"]:
                stale_table.add_row(item["file"], item["match"], item["actual"])
            console.print(stale_table)
        else:
            console.print("[green][OK] All documented test counts are up to date.[/green]")

        # Broken Links
        if audit["broken_links"]:
            links_table = Table(title="Broken Local file:// Links", box=box.SIMPLE_HEAVY)
            links_table.add_column("Source File", style="yellow")
            links_table.add_column("Link Text", style="white")
            links_table.add_column("Target Path", style="red")
            for b in audit["broken_links"]:
                links_table.add_row(b["file"], b["text"], b["target"])
            console.print(links_table)
        else:
            console.print("[green][OK] No broken local file links detected.[/green]")

    else:
        # Plain text fallback
        print("=== Branch-Aware Documentation Drift Report ===")
        print(f"Repository: {repo_root}")
        print(f"Branch: {current_branch} vs {main_branch}")
        if merge_base:
            print(f"Merge Base: {merge_base}")
        print(f"Changed Files: {len(changes)}")
        print(f"Active Tests: {test_count} in {module_count} modules")
        print(f"Audited Docs: {audit['audited_files_count']} files\n")

        print("--- Branch Commits ---")
        for h, msg in branch_commits[:15]:
            print(f"  {h} {msg}")
        if not branch_commits:
            print("  (no commits ahead of main)")

        print("\n--- Change Manifest ---")
        for category, info in sorted(categories.items()):
            targets = ", ".join(sorted(info["doc_targets"])) if info["doc_targets"] else "(no doc targets)"
            print(f"  [{category}] ({len(info['files'])} files) -> {targets}")
            for status, filepath in info["files"]:
                print(f"    {status} {filepath}")

        print("\n--- Documentation Targets Requiring Updates ---")
        for target in sorted(all_doc_targets):
            triggers = [cat for cat, info in categories.items() if target in info["doc_targets"]]
            print(f"  {target}  (triggered by: {', '.join(triggers)})")

        print("\n--- CLI Subcommands Missing in Docs ---")
        for cmd, desc in audit["missing_cli_in_docs"].items():
            print(f"  [MISSING] nousetsu {cmd}: {desc}")
        if not audit["missing_cli_in_docs"]:
            print("  All CLI commands are documented!")

        print("\n--- Stale Test Counts ---")
        for item in audit["stale_test_counts"]:
            print(f"  {item['file']}: Found '{item['match']}', expected '{item['actual']}'")
        if not audit["stale_test_counts"]:
            print("  All test counts match codebase!")

        print("\n--- Broken Links ---")
        for b in audit["broken_links"]:
            print(f"  {b['file']}: [{b['text']}]({b['target']})")
        if not audit["broken_links"]:
            print("  No broken file links detected!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
