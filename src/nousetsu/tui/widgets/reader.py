"""Dual-pane reader widget for source and translated text inspection."""
from typing import Optional
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
        border: solid $primary 30%;
        margin: 0;
        padding: 0 1;
    }
    .pane-title {
        color: $accent;
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
        border-bottom: solid $accent 30%;
        dock: top;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_source: Optional[str] = None
        self._last_target: Optional[str] = None
        self._source_widget: Optional[Static] = None
        self._target_widget: Optional[Markdown] = None

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(classes="reader-pane"):
                yield Label("📖 Source Text (Raw Chapter)", classes="pane-title")
                yield Static("Select a chapter from the list to view source text.", id="source_text_view")

            with VerticalScroll(classes="reader-pane"):
                yield Label("✨ Agent Translation (Polished Prose)", classes="pane-title")
                yield Markdown("*Translation preview will appear here.*", id="target_markdown_view")

    def on_mount(self) -> None:
        try:
            self._source_widget = self.query_one("#source_text_view", Static)
            self._target_widget = self.query_one("#target_markdown_view", Markdown)
        except Exception:
            pass

    def update_content(self, source_text: str, translated_markdown: str) -> None:
        """Update both panes with chapter content, avoiding redundant markdown re-parsing."""
        new_source = source_text or "(Empty source file)"
        new_target = translated_markdown or "*Translation pending or not yet generated.*"

        if self._source_widget is None:
            try:
                self._source_widget = self.query_one("#source_text_view", Static)
            except Exception:
                pass
        if self._target_widget is None:
            try:
                self._target_widget = self.query_one("#target_markdown_view", Markdown)
            except Exception:
                pass

        if new_source != self._last_source and self._source_widget:
            self._source_widget.update(new_source)
            self._last_source = new_source

        if new_target != self._last_target and self._target_widget:
            self._target_widget.update(new_target)
            self._last_target = new_target
