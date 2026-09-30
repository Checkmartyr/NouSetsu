# Token Analytics

This context defines project-level token reporting for translation work and how it relates to novel projects and their volume folders.

## Language

**Project**:
One novel’s working corpus and series data, distinct from other registered novels. A project may contain chapters grouped into volume folders.
_Avoid_: Workspace, all projects

**Volume Folder**:
A grouping of chapters within a project that can be selected as a narrower reporting scope.
_Avoid_: Project, volume (when referring to the folder itself)

**Project Token Analysis**:
A summary of recorded token usage for one project across all recorded attempts, covering all its volume folders by default and optionally scoped to one folder. It includes project totals and breakdowns by processing stage, model, and chapter, with no date-window filter. Trace records are authoritative for chapters that have them; metadata step usage fills gaps only for chapters without trace records, preventing double-counting.
_Avoid_: Chapter analytics (when referring to the project-wide summary)

**Recorded Token Usage**:
Token usage captured for translation work that actually occurred, including prompt, completion, thought, cached, and total counts. Partially processed, paused, or failed work is included when usage was recorded; work without recorded usage is not estimated. Metadata token totals without per-step usage are not considered recorded usage.
_Avoid_: Estimated usage, completed-only usage
