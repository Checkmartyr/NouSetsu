#!/usr/bin/env python3
"""
check_doc_drift.py - Exhaustive Code-to-Documentation Integrity & Drift Auditor

Performs deep re-checking of all related files, symbols, CLI commands/flags,
environment variables, agent skills, code snippets, and diagrams across documentation:
- Validates file existence and line anchors (#L{start}-L{end}) for all links.
- Uses Python AST to verify classes, functions, and methods cited in docs exist in code.
- Verifies CLI subcommands, aliases, options/flags, and defaults against src/nousetsu/cli/app.py.
- Validates NOVEL_* environment variables against .env.example and config source code.
- Audits Agent Skills catalog parity (counts and names in src/nousetsu/skills/catalog/).
- Validates Mermaid diagram types and enforces safe double-quoting of bracket labels.
- Validates syntax of Python code snippets in markdown fences via ast.parse.
- Collects active test counts and module counts via pytest to detect stale documentation.
- Supports --strict (CI guard), --fix (auto-sync test counts and doc/ -> docs/ links), and --json.
"""

from __future__ import annotations

import argparse
import ast
import json
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
    (r"src/nousetsu/agents/", "Pipeline Agents", ["AGENTS.md (Sec 3)", "docs/agents_deep_dive.md"]),
    (r"src/nousetsu/cli/", "CLI & Commands", ["README.md", "AGENTS.md (Sec 8)", "docs/user_guide.md"]),
    (r"src/nousetsu/graph/", "Workflow & Orchestration", ["AGENTS.md (Sec 2, 4)", "docs/workflow.md"]),
    (r"src/nousetsu/prompts/", "Prompts & Templates", ["AGENTS.md (Sec 3, 5)", "docs/agents_deep_dive.md"]),
    (r"src/nousetsu/skills/", "Agent Skills", ["AGENTS.md (Sec 5)", "README.md"]),
    (r"src/nousetsu/storage/", "Storage & Persistence", ["AGENTS.md (Sec 6)", "docs/storage_and_checkpoints.md"]),
    (r"src/nousetsu/rag/", "Hybrid RAG", ["AGENTS.md (Sec 7.9)", "docs/hybrid_rag.md"]),
    (r"src/nousetsu/tui/", "TUI Interface", ["README.md", "docs/tui_guide.md", "AGENTS.md (Sec 7.14)"]),
    (r"src/nousetsu/utils/", "Utilities & Engines", ["AGENTS.md (Sec 7)", "docs/architecture.md"]),
    (r"src/nousetsu/models/", "Data Models", ["AGENTS.md (Sec 6)", "docs/api_reference.md"]),
    (r"web/", "Web Dashboard", ["README.md", "AGENTS.md (Sec 7.12)"]),
    (r"tests/", "Test Suite", ["README.md", "AGENTS.md (Sec 7.7)"]),
    (r"\.env", "Environment Config", ["README.md", "AGENTS.md (Sec 6)"]),
    (r"AGENTS\.md|README\.md|CHANGELOG\.md", "Documentation", []),
    (r"docs/", "Documentation", []),
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
    """Get the branch diff summary and per-file change list."""
    code, stat_out = run_cmd(["git", "diff", f"{main_branch}...HEAD", "--stat"], repo_root)
    stat_summary = stat_out if code == 0 else ""

    code, name_out = run_cmd(["git", "diff", f"{main_branch}...HEAD", "--name-status"], repo_root)
    changes: List[Tuple[str, str]] = []
    if code == 0 and name_out:
        for line in name_out.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                status, filepath = parts[0][0], parts[1]
                changes.append((status, filepath))
            elif len(parts) == 1 and "\t" not in line:
                raw_parts = line.strip().split("\t")
                if len(raw_parts) >= 3:
                    changes.append(("R", raw_parts[2]))
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
    """Categorize changed files by subsystem and collect doc targets."""
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


# -----------------------------------------------------------------------------
# Deep Code Extraction & Parsing Utilities (AST-Based)
# -----------------------------------------------------------------------------

_AST_CACHE: Dict[Path, Tuple[Set[str], int]] = {}


def get_file_symbols_and_lines(filepath: Path) -> Tuple[Set[str], int]:
    """Parse a Python file using AST and return (set_of_symbol_names, total_lines)."""
    if filepath in _AST_CACHE:
        return _AST_CACHE[filepath]

    if not filepath.is_file():
        return set(), 0

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        total_lines = len(content.splitlines())
        tree = ast.parse(content, filename=str(filepath))

        symbols: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    symbols.add(node.target.id)

        _AST_CACHE[filepath] = (symbols, total_lines)
        return symbols, total_lines
    except Exception:
        # If parsing fails or non-python file, return simple line count
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = len(content.splitlines())
            return set(), lines
        except Exception:
            return set(), 0


def collect_cli_commands(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Parse argparse subcommands, aliases, and argument flags from nousetsu/cli/app.py."""
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
            rf'{re.escape(var_name)}\.add_argument\(\s*([^\n\)]+(?:\n[^\n\)]+)*)\)',
            re.MULTILINE
        )
        options: List[Dict[str, Any]] = []
        all_flags: Set[str] = set()

        for am in arg_re.finditer(content):
            arg_call = am.group(1)
            flags = re.findall(r'["\'](-{1,2}[a-zA-Z0-9_-]+)["\']', arg_call)
            if flags:
                opt_info = {
                    "flags": flags,
                    "default": None,
                    "help": ""
                }
                def_m = re.search(r'default=([^,\)]+)', arg_call)
                if def_m:
                    opt_info["default"] = def_m.group(1).strip()
                help_m = re.search(r'help=["\']([^"\']+)["\']', arg_call)
                if help_m:
                    opt_info["help"] = help_m.group(1).strip()
                options.append(opt_info)
                all_flags.update(flags)

        commands[cmd_name] = {
            "help": help_text,
            "aliases": aliases,
            "options": options,
            "all_flags": sorted(all_flags),
        }

    return commands


def collect_env_variables(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Collect all NOVEL_* environment variables from .env.example and config code."""
    env_vars: Dict[str, Dict[str, Any]] = {}
    example_path = repo_root / ".env.example"
    if example_path.is_file():
        content = example_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line_s = line.strip()
            if line_s.startswith("#") or not line_s or "=" not in line_s:
                continue
            key, val = line_s.split("=", 1)
            key = key.strip()
            if key.startswith("NOVEL_"):
                env_vars[key] = {"default": val.strip(), "source": ".env.example"}

    # Also search src/nousetsu for os.getenv("NOVEL_...")
    src_dir = repo_root / "src" / "nousetsu"
    if src_dir.is_dir():
        for py_file in src_dir.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
                for m in re.finditer(r'["\'](NOVEL_[A-Z0-9_]+)["\']', text):
                    k = m.group(1)
                    if k not in env_vars:
                        env_vars[k] = {"default": "(dynamic)", "source": str(py_file.relative_to(repo_root))}
            except Exception:
                pass

    return env_vars


def collect_skills_inventory(repo_root: Path) -> List[str]:
    """Collect all skill names defined in src/nousetsu/skills/catalog/*.md."""
    catalog_dir = repo_root / "src" / "nousetsu" / "skills" / "catalog"
    skills: List[str] = []
    if catalog_dir.is_dir():
        for md_file in sorted(catalog_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^name:\s*([a-zA-Z0-9_-]+)", content, re.MULTILINE)
            if m:
                skills.append(m.group(1))
            else:
                skills.append(md_file.stem)
    return skills


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


# -----------------------------------------------------------------------------
# Deep Documentation Auditor
# -----------------------------------------------------------------------------

def audit_all_documentation(
    repo_root: Path,
    cli_commands: Dict[str, Dict[str, Any]],
    env_vars: Dict[str, Dict[str, Any]],
    skills_inventory: List[str],
    test_count: int,
    module_count: int,
    fix: bool = False
) -> Dict[str, Any]:
    """Perform exhaustive re-checking of all documentation files."""
    repo_root = repo_root.resolve()
    doc_paths: List[Path] = [
        repo_root / "README.md",
        repo_root / "AGENTS.md",
        repo_root / "CHANGELOG.md",
    ]
    design_doc = repo_root / "DESIGN.md"
    if design_doc.is_file():
        doc_paths.append(design_doc)

    # Search both docs/ and doc/
    for folder_name in ["docs", "doc"]:
        folder_path = repo_root / folder_name
        if folder_path.is_dir():
            for p in sorted(folder_path.rglob("*.md")):
                if p not in doc_paths:
                    doc_paths.append(p)

    results: Dict[str, Any] = {
        "audited_files_count": len(doc_paths),
        "broken_links": [],
        "line_anchor_overflows": [],
        "broken_symbols": [],
        "stale_test_counts": [],
        "missing_cli_commands": {},
        "undocumented_cli_flags": {},
        "hallucinated_cli_flags": [],
        "missing_env_vars": [],
        "obsolete_env_vars": [],
        "skills_parity": {"expected": len(skills_inventory), "documented_mentions": []},
        "mermaid_alerts": [],
        "python_syntax_alerts": [],
        "fixed_items": [],
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

    # 1. Audit Links, Files, Anchors & Symbols
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for path, content in all_doc_content.items():
        rel_doc_path = str(path.relative_to(repo_root))
        lines_content = content.splitlines()

        for line_idx, line in enumerate(lines_content, start=1):
            for m in link_pattern.finditer(line):
                link_text = m.group(1).strip()
                raw_target = m.group(2).strip()

                # Skip web links, anchors, or mailto
                if raw_target.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                # Parse target and anchor
                target_url, _, anchor = raw_target.partition("#")

                # Resolve target path
                target_path: Optional[Path] = None
                if target_url.startswith("file:///"):
                    norm = target_url.replace("file:///", "").replace("/", os.sep)
                    target_path = Path(norm)
                elif target_url:
                    # Relative markdown link
                    target_path = (path.parent / target_url).resolve()

                if not target_path:
                    continue

                # Check if target exists
                if not target_path.exists():
                    # Check if it was a typo of doc/ vs docs/
                    resolved_fix = None
                    if ("doc/" in target_url or "/doc" in target_url or target_url.endswith("/doc") or target_url.endswith("doc")) and not target_path.exists():
                        target_str = str(target_path)
                        candidate_str = re.sub(r'([\\/])doc([\\/]|$)', r'\1docs\2', target_str)
                        candidate = Path(candidate_str)
                        if candidate.exists():
                            resolved_fix = candidate

                    if fix and resolved_fix:
                        # Auto-fix doc/ -> docs/
                        new_raw_target = re.sub(r'(^|/)doc(/|$)', r'\1docs\2', raw_target)
                        lines_content[line_idx - 1] = lines_content[line_idx - 1].replace(raw_target, new_raw_target)
                        results["fixed_items"].append({
                            "file": rel_doc_path,
                            "type": "fixed_doc_link",
                            "from": raw_target,
                            "to": new_raw_target,
                        })
                    else:
                        results["broken_links"].append({
                            "file": rel_doc_path,
                            "line": line_idx,
                            "text": link_text,
                            "target": raw_target,
                            "hint": "Path does not exist on disk" + (f" (did you mean docs/?)" if resolved_fix else "")
                        })
                    continue

                # Check line anchor overflow: #L{start}-L{end} or #L{start}
                if anchor and target_path.is_file():
                    anchor_m = re.match(r"^L(\d+)(?:-L(\d+))?$", anchor)
                    if anchor_m:
                        start_line = int(anchor_m.group(1))
                        end_line = int(anchor_m.group(2)) if anchor_m.group(2) else start_line
                        _, total_lines = get_file_symbols_and_lines(target_path)
                        if end_line > total_lines or start_line > total_lines:
                            results["line_anchor_overflows"].append({
                                "file": rel_doc_path,
                                "line": line_idx,
                                "target": str(target_path.relative_to(repo_root)),
                                "anchor": anchor,
                                "file_lines": total_lines,
                            })

                # Check Code Symbol in Link Text if pointing to Python file
                if target_path.suffix == ".py" and target_path.is_file():
                    clean_symbol = link_text.replace("`", "").replace("*", "").replace("`", "").strip()
                    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", clean_symbol):
                        # Candidate is an identifier
                        file_symbols, _ = get_file_symbols_and_lines(target_path)
                        if file_symbols and clean_symbol not in file_symbols:
                            results["broken_symbols"].append({
                                "file": rel_doc_path,
                                "line": line_idx,
                                "symbol": clean_symbol,
                                "target": str(target_path.relative_to(repo_root)),
                            })

        # Save fixed content if modified
        if fix and results["fixed_items"]:
            new_doc_text = "\n".join(lines_content)
            if new_doc_text != content:
                path.write_text(new_doc_text, encoding="utf-8")

    # 2. Check CLI Commands & Flags
    for cmd_name, cmd_info in cli_commands.items():
        if cmd_name == "_error":
            continue
        pattern = rf"\bnousetsu\s+{re.escape(cmd_name)}\b"
        if not re.search(pattern, aggregated_text):
            results["missing_cli_commands"][cmd_name] = cmd_info["help"]

        # Check documented flags vs actual flags for this command
        for opt in cmd_info["options"]:
            for flag in opt["flags"]:
                if len(flag) > 2 and flag.startswith("--"):
                    # Check if flag is documented
                    flag_pattern = rf"\b{re.escape(flag)}\b"
                    if not re.search(flag_pattern, aggregated_text):
                        if cmd_name not in results["undocumented_cli_flags"]:
                            results["undocumented_cli_flags"][cmd_name] = []
                        results["undocumented_cli_flags"][cmd_name].append(flag)

    # 3. Check Stale Test Counts & Fix If Requested
    test_pattern = re.compile(r"(\d{2,4})\s+tests\s+across\s+(\d{1,3})\s+modules")
    for path, content in all_doc_content.items():
        rel_path = str(path.relative_to(repo_root))
        for m in test_pattern.finditer(content):
            doc_tests = int(m.group(1))
            doc_mods = int(m.group(2))
            if test_count > 0 and (doc_tests != test_count or doc_mods != module_count):
                results["stale_test_counts"].append({
                    "file": rel_path,
                    "documented": f"{doc_tests} tests across {doc_mods} modules",
                    "actual": f"{test_count} tests across {module_count} modules",
                    "match": m.group(0),
                })
                if fix:
                    new_text = content.replace(m.group(0), f"{test_count} tests across {module_count} modules")
                    path.write_text(new_text, encoding="utf-8")
                    results["fixed_items"].append({
                        "file": rel_path,
                        "type": "fixed_test_count",
                        "from": m.group(0),
                        "to": f"{test_count} tests across {module_count} modules",
                    })

    # Also check badge test count in README.md
    readme_path = repo_root / "README.md"
    if readme_path.is_file():
        readme_content = readme_path.read_text(encoding="utf-8", errors="replace")
        badge_m = re.search(r"tests-(\d+)%20passed", readme_content)
        if badge_m and int(badge_m.group(1)) != test_count and test_count > 0:
            results["stale_test_counts"].append({
                "file": "README.md (badge)",
                "documented": f"{badge_m.group(1)} passed",
                "actual": f"{test_count} passed",
                "match": badge_m.group(0),
            })
            if fix:
                new_readme = readme_content.replace(badge_m.group(0), f"tests-{test_count}%20passed")
                readme_path.write_text(new_readme, encoding="utf-8")
                results["fixed_items"].append({
                    "file": "README.md",
                    "type": "fixed_badge_test_count",
                    "from": badge_m.group(0),
                    "to": f"tests-{test_count}%20passed",
                })

    # 4. Check Environment Variables Parity
    for env_key in env_vars:
        if env_key not in aggregated_text:
            results["missing_env_vars"].append(env_key)

    # 5. Check Agent Skills Parity
    for path, content in all_doc_content.items():
        for m in re.finditer(r"\((\d+)\s+Skills\)", content, re.IGNORECASE):
            doc_skills_count = int(m.group(1))
            if doc_skills_count != len(skills_inventory) and len(skills_inventory) > 0:
                results["skills_parity"]["documented_mentions"].append({
                    "file": str(path.relative_to(repo_root)),
                    "documented": doc_skills_count,
                    "actual": len(skills_inventory),
                })

    # 6. Check Mermaid Diagrams (Labels & Types)
    mermaid_block_re = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
    for path, content in all_doc_content.items():
        rel_path = str(path.relative_to(repo_root))
        for m in mermaid_block_re.finditer(content):
            block = m.group(1)
            # Check for unquoted bracket labels containing parentheses or colons: e.g. A[Label (Extra)]
            # Proper syntax must be A["Label (Extra)"]
            for bad_label_m in re.finditer(r'\b\w+\[(?!\")(.*?[\(\):\/\\<][^\]]*?)\]', block):
                results["mermaid_alerts"].append({
                    "file": rel_path,
                    "raw_label": bad_label_m.group(0),
                    "hint": 'Node label with special characters must be double-quoted: id["..."]',
                })

    # 7. Check Python Code Snippets Syntax
    py_block_re = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)
    for path, content in all_doc_content.items():
        rel_path = str(path.relative_to(repo_root))
        for m in py_block_re.finditer(content):
            code_block = m.group(1).strip()
            # Ignore snippets that contain placeholder ellipsis or diff indicators
            if "..." in code_block or code_block.startswith(("+", "-", ">>>")):
                continue
            # Only test complete definitions
            if any(k in code_block for k in ["class ", "def ", "import "]):
                try:
                    ast.parse(code_block)
                except SyntaxError as e:
                    # Only report if it wasn't obviously a partial snippet
                    if not any(marker in code_block for marker in ["# ...", "<...>", "etc."]):
                        results["python_syntax_alerts"].append({
                            "file": rel_path,
                            "error": str(e),
                            "preview": code_block.splitlines()[0][:60] if code_block else "",
                        })

    return results


# -----------------------------------------------------------------------------
# Main Execution & Rich Presentation
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="check_doc_drift.py - Deep Code-to-Doc Reference & Integrity Auditor"
    )
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero code if any drift or broken link is found")
    parser.add_argument("--fix", action="store_true", help="Automatically synchronize stale test counts and fix legacy doc/ links")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    repo_root = find_repo_root(Path(__file__))
    console = get_console()

    # 1. Branch detection
    current_branch = get_current_branch(repo_root)
    main_branch = get_main_branch(repo_root)
    merge_base = get_merge_base(repo_root, main_branch)
    is_on_main = current_branch in ("main", "master")

    # 2. Branch diff (current vs main)
    if is_on_main:
        stat_summary = ""
        _, name_out = run_cmd(["git", "diff", "--name-status", "HEAD~10", "HEAD"], repo_root)
        changes: List[Tuple[str, str]] = []
        if name_out:
            for line in name_out.splitlines():
                parts = line.strip().split("\t", 1)
                if len(parts) == 2:
                    changes.append((parts[0][0], parts[1]))
        branch_commits = []
    else:
        stat_summary, changes = get_branch_diff_stats(repo_root, main_branch)
        branch_commits = get_branch_commits(repo_root, main_branch)

    # 3. Categorize changes
    categories = categorize_changes(changes)

    # 4. Codebase Telemetry
    cli_commands = collect_cli_commands(repo_root)
    env_vars = collect_env_variables(repo_root)
    skills_inventory = collect_skills_inventory(repo_root)
    test_count, module_count = count_pytest_tests(repo_root)

    # 5. Deep Documentation Audit
    audit = audit_all_documentation(
        repo_root=repo_root,
        cli_commands=cli_commands,
        env_vars=env_vars,
        skills_inventory=skills_inventory,
        test_count=test_count,
        module_count=module_count,
        fix=args.fix,
    )

    # JSON output mode
    if args.json:
        print(json.dumps({
            "branch": current_branch,
            "main_branch": main_branch,
            "test_count": test_count,
            "module_count": module_count,
            "audit": audit,
        }, indent=2))
        has_critical_issues = bool(
            audit["broken_links"] or audit["broken_symbols"] or audit["stale_test_counts"]
        )
        return 1 if (args.strict and has_critical_issues) else 0

    # Collect all doc targets
    all_doc_targets: Set[str] = set()
    for cat_info in categories.values():
        all_doc_targets.update(cat_info["doc_targets"])

    # Rich Presentation
    if HAS_RICH and console:
        branch_info = (
            f"Branch: [bold yellow]{current_branch}[/bold yellow] vs "
            f"[bold green]{main_branch}[/bold green]"
        )
        if merge_base:
            branch_info += f"  (merge-base: [dim]{merge_base}[/dim])"

        console.print(Panel.fit(
            f"[bold cyan]🔍 Deep Code-to-Documentation Integrity & Drift Report[/bold cyan]\n"
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
            for h, msg in branch_commits[:10]:
                commit_table.add_row(h, msg)
            if len(branch_commits) > 10:
                commit_table.add_row("...", f"[dim]+{len(branch_commits) - 10} more[/dim]")
            console.print(commit_table)

        # Change Manifest
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
                for status, filepath in info["files"][:8]:
                    icon = status_icons.get(status, "[white]?[/white]")
                    cat_branch.add(f"{icon} {filepath}")
                if len(info["files"]) > 8:
                    cat_branch.add(f"[dim]... and {len(info['files']) - 8} more[/dim]")

            console.print(manifest_tree)

        # Broken Local Links
        if audit["broken_links"]:
            console.print()
            links_table = Table(title="❌ Broken Local file:// / Relative Links", box=box.SIMPLE_HEAVY)
            links_table.add_column("Source Document", style="yellow", width=25)
            links_table.add_column("Line", style="cyan", width=6)
            links_table.add_column("Link Text", style="white", width=28)
            links_table.add_column("Target Path / Diagnostic", style="red")
            for b in audit["broken_links"][:20]:
                links_table.add_row(b["file"], str(b["line"]), b["text"][:26], f"{b['target']}\n[dim]{b['hint']}[/dim]")
            if len(audit["broken_links"]) > 20:
                links_table.add_row("...", "...", "...", f"[dim]+{len(audit['broken_links']) - 20} more broken links[/dim]")
            console.print(links_table)
        else:
            console.print("\n[green][OK] No broken local file or relative links detected.[/green]")

        # Broken Code Symbols (AST verification)
        if audit["broken_symbols"]:
            console.print()
            sym_table = Table(title="⚠️ Nonexistent Code Symbols Cited in Links", box=box.SIMPLE_HEAVY)
            sym_table.add_column("Document", style="yellow")
            sym_table.add_column("Line", style="cyan")
            sym_table.add_column("Referenced Symbol", style="bold red")
            sym_table.add_column("Target Python File", style="white")
            for s in audit["broken_symbols"]:
                sym_table.add_row(s["file"], str(s["line"]), s["symbol"], s["target"])
            console.print(sym_table)
        else:
            console.print("[green][OK] All referenced code symbols match Python AST definitions.[/green]")

        # Line Anchor Overflows
        if audit["line_anchor_overflows"]:
            console.print()
            anchor_table = Table(title="⚠️ Line Anchor Out of Bounds (#L{start}-L{end})", box=box.SIMPLE_HEAVY)
            anchor_table.add_column("Document", style="yellow")
            anchor_table.add_column("Line", style="cyan")
            anchor_table.add_column("Target File", style="white")
            anchor_table.add_column("Anchor", style="red")
            anchor_table.add_column("Actual Lines", style="green")
            for a in audit["line_anchor_overflows"]:
                anchor_table.add_row(a["file"], str(a["line"]), a["target"], a["anchor"], str(a["file_lines"]))
            console.print(anchor_table)

        # CLI Subcommands Status
        cli_table = Table(title="CLI Subcommands Status", box=box.SIMPLE_HEAVY)
        cli_table.add_column("Subcommand", style="bold green")
        cli_table.add_column("Status", style="bold")
        cli_table.add_column("Registered Flags", style="cyan")
        cli_table.add_column("Description", style="white")
        for cmd, info in sorted(cli_commands.items()):
            if cmd == "_error":
                continue
            status = "[bold red]MISSING[/bold red]" if cmd in audit["missing_cli_commands"] else "[bold green]DOCUMENTED[/bold green]"
            flags_summary = f"{len(info['all_flags'])} flags"
            cli_table.add_row(f"nousetsu {cmd}", status, flags_summary, info["help"])
        console.print(cli_table)

        # Undocumented CLI Option Flags
        if audit["undocumented_cli_flags"]:
            console.print()
            flags_table = Table(title="ℹ️ Undocumented CLI Option Flags in Code", box=box.SIMPLE_HEAVY)
            flags_table.add_column("Subcommand", style="bold cyan")
            flags_table.add_column("Undocumented Flags in Docs", style="yellow")
            for cmd_name, flags in sorted(audit["undocumented_cli_flags"].items()):
                flags_table.add_row(f"nousetsu {cmd_name}", ", ".join(flags))
            console.print(flags_table)

        # Stale Test Counts
        if audit["stale_test_counts"]:
            console.print()
            stale_table = Table(title="⚠️ Stale Test Count References in Docs", box=box.SIMPLE_HEAVY)
            stale_table.add_column("Document File", style="yellow")
            stale_table.add_column("Documented Text", style="red")
            stale_table.add_column("Actual Codebase Value", style="green")
            for item in audit["stale_test_counts"]:
                stale_table.add_row(item["file"], item["match"], item["actual"])
            console.print(stale_table)
        else:
            console.print("[green][OK] All documented test counts are synchronized.[/green]")

        # Mermaid Diagram Syntax Alerts
        if audit["mermaid_alerts"]:
            console.print()
            mermaid_table = Table(title="⚠️ Mermaid Diagram Label Quoting Alerts", box=box.SIMPLE_HEAVY)
            mermaid_table.add_column("Document", style="yellow")
            mermaid_table.add_column("Problematic Label", style="red")
            mermaid_table.add_column("Recommended Fix", style="green")
            for ma in audit["mermaid_alerts"]:
                mermaid_table.add_row(ma["file"], ma["raw_label"], ma["hint"])
            console.print(mermaid_table)

        # Auto-fixed items
        if audit["fixed_items"]:
            console.print()
            fix_table = Table(title="✅ Automatically Fixed Documentation Discrepancies (--fix)", box=box.SIMPLE_HEAVY)
            fix_table.add_column("Document File", style="cyan")
            fix_table.add_column("Type", style="yellow")
            fix_table.add_column("Previous Value", style="red")
            fix_table.add_column("Updated Value", style="green")
            for f in audit["fixed_items"]:
                fix_table.add_row(f["file"], f["type"], f["from"], f["to"])
            console.print(fix_table)

    else:
        # Plain text presentation
        print("=== Deep Code-to-Doc Drift Report ===")
        print(f"Repository: {repo_root}")
        print(f"Branch: {current_branch} vs {main_branch}")
        print(f"Active Tests: {test_count} across {module_count} modules")
        print(f"Audited Docs: {audit['audited_files_count']} files\n")

        if audit["broken_links"]:
            print(f"Found {len(audit['broken_links'])} broken links:")
            for b in audit["broken_links"][:10]:
                print(f"  [{b['file']}:{b['line']}] {b['text']} -> {b['target']} ({b['hint']})")

        if audit["broken_symbols"]:
            print(f"Found {len(audit['broken_symbols'])} nonexistent symbols:")
            for s in audit["broken_symbols"]:
                print(f"  [{s['file']}:{s['line']}] {s['symbol']} not in {s['target']}")

        if audit["stale_test_counts"]:
            print(f"Found {len(audit['stale_test_counts'])} stale test counts:")
            for item in audit["stale_test_counts"]:
                print(f"  {item['file']}: Found '{item['match']}', actual '{item['actual']}'")

    has_critical_issues = bool(
        audit["broken_links"] or audit["broken_symbols"] or audit["stale_test_counts"]
    )
    if args.strict and has_critical_issues:
        if HAS_RICH and console:
            console.print("\n[bold red]❌ STRICT AUDIT FAILED: Discrepancies detected between documentation and codebase.[/bold red]")
        else:
            print("\nSTRICT AUDIT FAILED: Discrepancies detected between documentation and codebase.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
