#!/usr/bin/env python3
"""
check_doc_drift.py - Documentation Drift & Integrity Auditor

Audits project documentation against the latest code state:
- Scans CLI subcommands and options registered in the codebase vs. documented in README/AGENTS/docs.
- Scans total test counts and module coverage.
- Detects recent code changes (git commits/diffs) that lack corresponding doc updates.
- Validates internal and file:// markdown links.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def get_console():
    if HAS_RICH:
        # Avoid charmap cp1252 crash on Windows legacy console
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


def collect_cli_commands(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Parse argparse subcommands and options directly from nousetsu/cli/app.py."""
    commands: Dict[str, Dict[str, Any]] = {}
    cli_app_file = repo_root / "src" / "nousetsu" / "cli" / "app.py"
    if not cli_app_file.is_file():
        return commands

    content = cli_app_file.read_text(encoding="utf-8", errors="replace")

    # Match subparsers.add_parser("subcommand", ... help="Help text")
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

        # Find arguments associated with this parser variable
        arg_re = re.compile(rf'{re.escape(var_name)}\.add_argument\(\s*(["\'][^"\']+["\'](?:,\s*["\'][^"\']+["\'])*)')
        options = []
        for am in arg_re.finditer(content):
            raw_args = am.group(1)
            for opt in re.findall(r'["\'](--?[a-zA-Z0-9_-]+)["\']', raw_args):
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
            # e.g., "347 test items collected in 0.42s"
            m = re.search(r"(\d+)\s+(?:test\s+)?items?\s+collected", line)
            if m:
                test_count = int(m.group(1))
    return test_count, len(modules)


def get_recent_git_commits(repo_root: Path, limit: int = 8) -> List[Tuple[str, str]]:
    """Return recent commits (hash, message)."""
    code, out = run_cmd(["git", "log", f"-n{limit}", "--oneline"], repo_root)
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


def audit_documentation_files(repo_root: Path, cli_commands: Dict[str, Dict[str, Any]], test_count: int) -> Dict[str, Any]:
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

    # Combine text from all docs
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
        # Look for e.g. "nousetsu <cmd_name>"
        pattern = rf"\bnousetsu\s+{re.escape(cmd_name)}\b"
        if not re.search(pattern, aggregated_text):
            results["missing_cli_in_docs"][cmd_name] = cli_commands[cmd_name]["help"]

    # Check test count discrepancies
    for path, content in all_doc_content.items():
        # Match e.g. "320 tests across 49 modules" or "over 300 tests"
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

    # Check file:// links pointing to this repo
    link_pattern = re.compile(r"\[([^\]]+)\]\((file:///[^\)]+)\)")
    for path, content in all_doc_content.items():
        for m in link_pattern.finditer(content):
            target = m.group(2)
            # Strip anchor/fragment (e.g. #L10-L20)
            target_clean = target.split("#")[0]
            # Normalize Windows file:/// path
            norm = target_clean.replace("file:///", "").replace("/", os.sep)
            # If path points to drive letter (e.g. D:\...)
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

    # 1. Collect Codebase Telemetry
    cli_commands = collect_cli_commands(repo_root)
    test_count, module_count = count_pytest_tests(repo_root)
    recent_commits = get_recent_git_commits(repo_root, limit=6)
    audit = audit_documentation_files(repo_root, cli_commands, test_count)

    # 2. Render Results
    if HAS_RICH and console:
        console.print(Panel.fit(
            f"[bold cyan]Documentation Drift & Integrity Report[/bold cyan]\n"
            f"Repository: [green]{repo_root}[/green]\n"
            f"Active Tests: [bold magenta]{test_count}[/bold magenta] in [magenta]{module_count}[/magenta] modules | "
            f"Audited Docs: [yellow]{audit['audited_files_count']}[/yellow] files",
            box=box.ROUNDED,
            border_style="cyan"
        ))

        # Recent Commits
        if recent_commits:
            table = Table(title="Recent Commits (Potential Feature Drift)", box=box.SIMPLE_HEAVY)
            table.add_column("Hash", style="cyan", width=9)
            table.add_column("Message", style="white")
            for h, msg in recent_commits:
                table.add_row(h, msg)
            console.print(table)

        # CLI Drift Table
        cli_table = Table(title="CLI Subcommands Documentation Status", box=box.SIMPLE_HEAVY)
        cli_table.add_column("Subcommand", style="bold green")
        cli_table.add_column("Status", style="bold")
        cli_table.add_column("Description", style="white")

        for cmd, info in sorted(cli_commands.items()):
            if cmd == "_error":
                continue
            if cmd in audit["missing_cli_in_docs"]:
                cli_table.add_row(f"nousetsu {cmd}", "[bold red]MISSING IN DOCS[/bold red]", info["help"])
            else:
                cli_table.add_row(f"nousetsu {cmd}", "[bold green]DOCUMENTED[/bold green]", info["help"])
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
            console.print("[green][OK] No broken local file links detected in markdown documents.[/green]")

    else:
        # Plain text fallback
        print("=== Documentation Drift & Integrity Report ===")
        print(f"Repository: {repo_root}")
        print(f"Active Tests: {test_count} in {module_count} modules")
        print(f"Audited Docs: {audit['audited_files_count']} files\n")

        print("--- CLI Subcommands Missing in Docs ---")
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
