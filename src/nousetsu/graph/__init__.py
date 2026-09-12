from typing import TYPE_CHECKING
from nousetsu.graph.procedural import (
    ProceduralGraph,
    ProceduralNode,
    ProceduralEdge,
    ProceduralNodeType,
    ProceduralRelation,
    get_default_extractor_graph,
    get_default_drafter_graph
)
from nousetsu.graph.pg_refiner import DiagnosticTrace, ProceduralGraphRefiner

if TYPE_CHECKING:
    from nousetsu.graph.workflow import NovelTranslationWorkflow


def __getattr__(name: str):
    if name == "NovelTranslationWorkflow":
        from nousetsu.graph.workflow import NovelTranslationWorkflow
        return NovelTranslationWorkflow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "NovelTranslationWorkflow",
    "ProceduralGraph",
    "ProceduralNode",
    "ProceduralEdge",
    "ProceduralNodeType",
    "ProceduralRelation",
    "get_default_extractor_graph",
    "get_default_drafter_graph",
    "ProceduralGraphRefiner",
    "DiagnosticTrace"
]

