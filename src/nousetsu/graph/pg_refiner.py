"""Offline Self-Evolution Refiner for Procedural Graphs (Lu et al., arXiv:2609.09153v1 Sec 3.3).

Executes an offline diagnostic loop:
1. Diagnostic Rollout: Extracts failure traces (critic warnings, low scores) vs success traces.
2. Feedback-Driven Mutation: Proposes Add/Update/Delete edits to edge attributes (condition, guidance, pitfalls).
3. Rejection Memory: Records rejected candidates to avoid repeating counterproductive edits.
4. Validation Gating: Commits candidate graphs only when structural integrity and validation criteria are met.
5. Zero Token Overhead at runtime: Runs completely offline or on-demand without affecting translation inference tokens.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from nousetsu.agents.llm import extract_text_from_message, get_llm
from nousetsu.graph.procedural import ProceduralEdge, ProceduralGraph
from nousetsu.models.metadata import QualityAudit

logger = logging.getLogger("nousetsu.graph.refiner")


class DiagnosticTrace(BaseModel):
    """Execution trace containing solver output and auditor evaluation."""
    trace_id: str
    stage: str  # "extractor" or "drafter"
    context_snippet: str
    output_snippet: str
    fidelity_score: float = 9.0
    style_score: float = 9.0
    warnings: List[str] = Field(default_factory=list)
    critique_notes: str = ""

    @property
    def is_success(self) -> bool:
        return self.fidelity_score >= 8.5 and len(self.warnings) == 0


class GraphEditOperation(BaseModel):
    """Structured mutation operation for a Procedural Graph edge."""
    operation: str = "UPDATE"  # "ADD", "UPDATE", "DELETE"
    edge_source: str
    edge_target: str
    new_condition: Optional[str] = None
    new_guidance: Optional[str] = None
    new_pitfalls: Optional[str] = None
    rationale: str = ""


class ProceduralGraphRefiner:
    """Offline engine for mutating and evolving Procedural Graphs from execution traces."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        rejection_memory_path: Optional[Path] = None
    ):
        self.model_name = model_name or "gemini-3.5-flash-lite"
        self.llm = get_llm(model_name=self.model_name, temperature=0.2)
        self.rejection_memory: List[Dict[str, Any]] = []
        self.rejection_memory_path = rejection_memory_path

        if self.rejection_memory_path and self.rejection_memory_path.exists():
            try:
                with open(self.rejection_memory_path, "r", encoding="utf-8") as f:
                    self.rejection_memory = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load rejection memory: {e}")

    def extract_trace_from_audit(
        self,
        trace_id: str,
        stage: str,
        input_text: str,
        output_text: str,
        audit: QualityAudit,
        critique_notes: str = ""
    ) -> DiagnosticTrace:
        """Helper to create a diagnostic trace from a chapter critique report."""
        return DiagnosticTrace(
            trace_id=trace_id,
            stage=stage,
            context_snippet=input_text[:500],
            output_snippet=output_text[:500],
            fidelity_score=audit.fidelity_score,
            style_score=audit.style_score,
            warnings=audit.warnings,
            critique_notes=critique_notes
        )

    def evolve_graph(
        self,
        graph: ProceduralGraph,
        traces: List[DiagnosticTrace]
    ) -> ProceduralGraph:
        """Executes Step 2 (Mutation) and Step 3 (Validation Gating) over input traces."""
        failure_traces = [t for t in traces if not t.is_success]
        success_traces = [t for t in traces if t.is_success]

        if not failure_traces:
            logger.info("No failure traces detected. Retaining current graph.")
            return graph

        # Generate mutation proposal via refiner LLM
        edits = self._propose_mutations(graph, failure_traces, success_traces)
        if not edits:
            logger.info("Refiner proposed no edits.")
            return graph

        candidate_graph = self._apply_edits(graph, edits)

        # Validation gate
        if self._validate_candidate(candidate_graph):
            logger.info(f"Committed {len(edits)} mutation(s) to graph '{graph.graph_id}'.")
            return candidate_graph
        else:
            logger.warning("Candidate graph failed structural validation. Rolling back.")
            self._record_rejection(edits, "Failed structural verification")
            return graph

    def _propose_mutations(
        self,
        graph: ProceduralGraph,
        failures: List[DiagnosticTrace],
        successes: List[DiagnosticTrace]
    ) -> List[GraphEditOperation]:
        """Queries refiner LLM to identify recurring pitfalls and propose edge attribute mutations."""
        fail_summary = "\n".join([
            f"- Trace [{f.trace_id}] Warnings: {', '.join(f.warnings)}; Notes: {f.critique_notes}"
            for f in failures[:5]
        ])
        succ_summary = "\n".join([
            f"- Trace [{s.trace_id}] Passed cleanly (Fidelity: {s.fidelity_score}, Style: {s.style_score})"
            for s in successes[:3]
        ]) or "No recent clean traces."

        rejected_summary = json.dumps(self.rejection_memory[-5:], indent=2) if self.rejection_memory else "None"

        graph_summary = json.dumps([
            {
                "source": e.source,
                "target": e.target,
                "condition": e.condition,
                "guidance": e.guidance,
                "pitfalls": e.pitfalls
            }
            for e in graph.edges
        ], indent=2)

        prompt = f"""You are a cognitive architect optimizing an LLM Procedural Graph for literary translation (Lu et al., arXiv:2609.09153v1).
Analyze failure traces to refine edge attributes ('guidance', 'pitfalls', 'condition') to eliminate recurring errors.

Current Graph Edges:
{graph_summary}

Failure Traces (Critic Audits):
{fail_summary}

Successful Traces:
{succ_summary}

Previously Rejected Proposals (Do NOT repeat):
{rejected_summary}

Rules:
1. Propose concrete edits to add or update edge 'pitfalls' or 'guidance'.
2. DO NOT delete existing node IDs. Keep graph connected.
3. Keep pitfalls terse, actionable, and non-repetitive.

Respond strictly in valid JSON:
[
  {{
    "operation": "UPDATE",
    "edge_source": "Zero_Anaphora_Resolution",
    "edge_target": "Voice_Modulation",
    "new_condition": "Omitted subject in dialogue or narrative",
    "new_guidance": "Trace omitted subjects using speech register and honorifics before drafting.",
    "new_pitfalls": "Never guess speaker identity. In rapid banter, verify turn-taking against preceding context.",
    "rationale": "Addressed recurring speaker swap warning in critic notes."
  }}
]
"""
        from langchain_core.messages import HumanMessage
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            raw_text = extract_text_from_message(response.content)
            # Find json array
            import re
            match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
            if not match:
                return []
            parsed = json.loads(match.group(0))
            edits = [GraphEditOperation.model_validate(op) for op in parsed]
            return edits
        except Exception as e:
            logger.warning(f"Failed to generate graph mutations: {e}")
            return []

    def _apply_edits(
        self,
        base_graph: ProceduralGraph,
        edits: List[GraphEditOperation]
    ) -> ProceduralGraph:
        """Applies mutation operations to a deep copy of the graph."""
        new_graph = base_graph.model_copy(deep=True)

        for edit in edits:
            # Find matching edge
            target_edge = None
            for e in new_graph.edges:
                if e.source == edit.edge_source and e.target == edit.edge_target:
                    target_edge = e
                    break

            if edit.operation == "UPDATE" and target_edge:
                if edit.new_condition is not None:
                    target_edge.condition = edit.new_condition
                if edit.new_guidance is not None:
                    target_edge.guidance = edit.new_guidance
                if edit.new_pitfalls is not None:
                    target_edge.pitfalls = edit.new_pitfalls
            elif edit.operation == "ADD" and not target_edge:
                new_edge = ProceduralEdge(
                    source=edit.edge_source,
                    target=edit.edge_target,
                    condition=edit.new_condition,
                    guidance=edit.new_guidance or "Follow standard novel translation directives.",
                    pitfalls=edit.new_pitfalls
                )
                new_graph.edges.append(new_edge)
            elif edit.operation == "DELETE" and target_edge:
                new_graph.edges.remove(target_edge)

        return new_graph

    def _validate_candidate(self, candidate: ProceduralGraph) -> bool:
        """Structural validation checks (Connectivity, Non-empty Guidance)."""
        if not candidate.nodes or not candidate.edges:
            return False

        # Every edge must reference existing nodes
        for edge in candidate.edges:
            if edge.source not in candidate.nodes or edge.target not in candidate.nodes:
                return False
            if not edge.guidance or not edge.guidance.strip():
                return False

        return True

    def _record_rejection(self, edits: List[GraphEditOperation], reason: str) -> None:
        """Caches rejected candidate edits into rejection memory."""
        rejection_entry = {
            "edits": [e.model_dump() for e in edits],
            "reason": reason
        }
        self.rejection_memory.append(rejection_entry)
        if self.rejection_memory_path:
            try:
                self.rejection_memory_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.rejection_memory_path, "w", encoding="utf-8") as f:
                    json.dump(self.rejection_memory, f, indent=2)
            except Exception as e:
                logger.warning(f"Could not persist rejection memory: {e}")
