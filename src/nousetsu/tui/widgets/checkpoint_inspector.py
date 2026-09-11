"""Widget displaying metadata, quality scores, and stage checkpoints."""
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, Static
from nousetsu.models.metadata import ChapterMetadata, StageStatus
from nousetsu.utils.formatting import format_duration


class CheckpointInspectorWidget(Widget):
    """Bottom inspection bar showing checkpoint state and quality audit."""

    DEFAULT_CSS = """
    CheckpointInspectorWidget {
        height: 5;
        border: solid $accent 40%;
        padding: 0 1;
        background: $surface;
        margin: 0;
    }
    .inspector-col {
        width: 1fr;
        height: auto;
    }
    .inspector-col-wide {
        width: 2fr;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(classes="inspector-col"):
                yield Static("Status: [dim]Unprocessed[/]", id="lbl_status")
                yield Static("Stage: -", id="lbl_stage")
                yield Static("Hash: -", id="lbl_hash")

            with Vertical(classes="inspector-col"):
                yield Static("Tokens: -", id="lbl_tokens")
                yield Static("Fidelity: -", id="lbl_fidelity")
                yield Static("Style: -", id="lbl_style")

            with Vertical(classes="inspector-col-wide"):
                yield Static("Glossary: -", id="lbl_glossary")
                yield Static("Terms: -", id="lbl_terms")
                yield Static("Warnings: None", id="lbl_warnings")

    def update_metadata(self, meta: Optional[ChapterMetadata]) -> None:
        """Update inspection labels based on chapter metadata."""
        lbl_status = self.query_one("#lbl_status", Static)
        lbl_stage = self.query_one("#lbl_stage", Static)
        lbl_hash = self.query_one("#lbl_hash", Static)
        lbl_fidelity = self.query_one("#lbl_fidelity", Static)
        lbl_style = self.query_one("#lbl_style", Static)
        lbl_glossary = self.query_one("#lbl_glossary", Static)
        lbl_tokens = self.query_one("#lbl_tokens", Static)
        lbl_warnings = self.query_one("#lbl_warnings", Static)
        lbl_terms = self.query_one("#lbl_terms", Static)

        if not meta:
            lbl_status.update("Status: [dim]Unprocessed / Pending[/]")
            lbl_stage.update("Stage: NONE")
            lbl_hash.update("Hash: -")
            lbl_fidelity.update("Fidelity: -")
            lbl_style.update("Style: -")
            lbl_glossary.update("Glossary: -")
            lbl_tokens.update("Tokens: -")
            lbl_warnings.update("Warnings: None")
            lbl_terms.update("Terms: None")
            return

        status_str = meta.checkpoint.status.value.upper()
        if meta.checkpoint.status == StageStatus.COMPLETED:
            status_display = f"Status: [bold green]{status_str}[/]"
            lbl_stage.update(f"Stage: [cyan]{meta.checkpoint.last_completed_stage.value.upper()}[/]")
        elif meta.checkpoint.status == StageStatus.FAILED:
            failed_stage_name = (meta.checkpoint.failed_stage.value if meta.checkpoint.failed_stage else meta.checkpoint.last_completed_stage.value).upper()
            err_type = meta.checkpoint.last_error_type or "Error"
            status_display = f"Status: [bold red]{status_str}[/] ({err_type})"
            lbl_stage.update(f"Failed at: [bold red]{failed_stage_name}[/]")
        else:
            status_display = f"Status: [yellow]{status_str}[/]"
            lbl_stage.update(f"Stage: [cyan]{meta.checkpoint.last_completed_stage.value.upper()}[/]")

        lbl_status.update(status_display)
        lbl_hash.update(f"SHA: {meta.source_sha256[:10]}...")

        lbl_fidelity.update(f"Fidelity: [bold cyan]{meta.quality_audit.fidelity_score:.1f}[/]/10")
        lbl_style.update(f"Style: [bold cyan]{meta.quality_audit.style_score:.1f}[/]/10")
        lbl_glossary.update(f"Glossary: {meta.quality_audit.glossary_compliance_pct:.0f}%")
        dur_str = f" in {format_duration(meta.stats.duration_seconds)}" if meta.stats.duration_seconds > 0 else ""
        if meta.stats.total_tokens:
            lbl_tokens.update(f"Tokens: [bold green]{meta.stats.total_tokens:,}[/]{dur_str} (In:{meta.stats.prompt_tokens:,} Out:{meta.stats.completion_tokens:,})")
        else:
            lbl_tokens.update(f"Tokens: -{dur_str}")

        if meta.checkpoint.status == StageStatus.FAILED:
            err_snippet = (meta.checkpoint.last_error or 'Unknown error')[:45]
            retries = meta.checkpoint.retry_count
            lbl_warnings.update(f"[bold red]❌ {err_snippet}...\n(Retries: {retries}, Logs: {len(meta.checkpoint.error_logs)})[/]")
        elif meta.quality_audit.warnings:
            warn_text = "\n".join([f"⚠️ {w}" for w in meta.quality_audit.warnings[:2]])
            lbl_warnings.update(warn_text)
        else:
            lbl_warnings.update("[green]✓ Clean (No warnings)[/]")

        if meta.glossary_terms_applied:
            terms_text = ", ".join([f"{t.source}->{t.target}" for t in meta.glossary_terms_applied[:3]])
            lbl_terms.update(f"Terms: {terms_text}")
        else:
            lbl_terms.update("Terms: None")
