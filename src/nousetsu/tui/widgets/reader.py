"""Dual-pane reader widget for source and translated text inspection."""
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static


class DualReaderWidget(Widget):
    """Side-by-side viewer displaying source text alongside agent translation."""

    DEFAULT_CSS = """
    DualReaderWidget {
        layout: horizontal;
        height: 1fr;
    }
    .reader-pane {
        width: 1fr;
        height: 1fr;
        border: round $primary;
        margin: 0 1;
        padding: 0 1;
    }
    .pane-title {
        background: $accent;
        color: $text;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 1;
        dock: top;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(classes="reader-pane"):
                yield Label("📖 Source Text (Raw Chapter)", classes="pane-title")
                yield Static("Select a chapter from the list to view source text.", id="source_text_view")

            with VerticalScroll(classes="reader-pane"):
                yield Label("✨ Agent Translation (Polished Prose)", classes="pane-title")
                yield Markdown("*Translation preview will appear here.*", id="target_markdown_view")

    def update_content(self, source_text: str, translated_markdown: str) -> None:
        """Update both panes with chapter content."""
        source_widget = self.query_one("#source_text_view", Static)
        target_widget = self.query_one("#target_markdown_view", Markdown)

        source_widget.update(source_text or "(Empty source file)")
        target_widget.update(translated_markdown or "*Translation pending or not yet generated.*")
