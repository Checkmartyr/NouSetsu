"""Procedural Graph implementation for LLM agent execution structures (Lu et al., arXiv:2609.09153v1).

Provides explicit attributed directed graphs G = (V, R, E, Phi) where:
- Nodes (V) represent cognitive states or operational procedures.
- Edges (E) represent permissible transitions (u, r, v).
- Attributes (Phi) associate edges with (condition, guidance, pitfalls).
Supports deterministic localization to extract active subgraphs without runtime LLM guidance overhead.
"""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ProceduralNodeType(str, Enum):
    STATE = "STATE"
    ACTION = "ACTION"
    VERIFICATION = "VERIFICATION"


class ProceduralRelation(str, Enum):
    LEADS_TO = "LEADS_TO"
    TRIGGERS = "TRIGGERS"
    REQUIRES = "REQUIRES"
    PROVIDES_INPUT_FOR = "PROVIDES_INPUT_FOR"


class ProceduralNode(BaseModel):
    id: str
    name: str
    node_type: ProceduralNodeType = ProceduralNodeType.ACTION
    description: str


class ProceduralEdge(BaseModel):
    source: str
    target: str
    relation: ProceduralRelation = ProceduralRelation.LEADS_TO
    condition: Optional[str] = None
    guidance: str
    pitfalls: Optional[str] = None


class ProceduralGraph(BaseModel):
    """Attributed directed graph of procedural knowledge for agent steering."""
    graph_id: str
    description: str
    nodes: Dict[str, ProceduralNode] = Field(default_factory=dict)
    edges: List[ProceduralEdge] = Field(default_factory=list)

    def add_node(self, node: ProceduralNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: ProceduralEdge) -> None:
        self.edges.append(edge)

    def localize(self, current_node_id: str, max_hops: int = 1) -> List[ProceduralEdge]:
        """Extracts outgoing edges reachable within max_hops from the active node.
        
        This implements the localized neighborhood N_h(u_t) from Section 3.2 of the paper
        deterministically without requiring an online guidance LLM.
        """
        if current_node_id not in self.nodes:
            # Fallback to all edges if node not found
            return self.edges

        visited_nodes = {current_node_id}
        active_frontier = {current_node_id}
        localized_edges: List[ProceduralEdge] = []

        for _ in range(max_hops):
            next_frontier = set()
            for edge in self.edges:
                if edge.source in active_frontier:
                    localized_edges.append(edge)
                    if edge.target not in visited_nodes:
                        next_frontier.add(edge.target)
                        visited_nodes.add(edge.target)
            active_frontier = next_frontier
            if not active_frontier:
                break

        return localized_edges if localized_edges else self.edges

    def to_compact_guidance(
        self,
        current_node_id: str,
        max_hops: int = 1,
        header: str = "PROCEDURAL DIRECTIVES (Procedural Graph Guidance)"
    ) -> str:
        """Serializes localized subgraph into a token-frugal markdown section (<100 tokens)."""
        edges = self.localize(current_node_id, max_hops=max_hops)
        if not edges:
            return ""

        lines = [f"## {header}:"]
        for edge in edges:
            target_node = self.nodes.get(edge.target)
            target_name = target_node.name if target_node else edge.target
            cond_str = f" [When: {edge.condition}]" if edge.condition else ""
            lines.append(f"- Step -> {target_name}{cond_str}: {edge.guidance}")
            if edge.pitfalls:
                lines.append(f"  * Pitfalls to Avoid: {edge.pitfalls}")

        return "\n".join(lines)


# =========================================================================
# Default Expert Priors for Extractor and Drafter (arXiv:2609.09153v1 Sec 3.1)
# =========================================================================

def get_default_extractor_graph() -> ProceduralGraph:
    """Returns the default Procedural Graph for Entity and Terminology Extraction."""
    g = ProceduralGraph(
        graph_id="extractor_default_v1",
        description="Procedural execution graph for literary entity and terminology extraction."
    )
    # Nodes
    g.add_node(ProceduralNode(id="Scan_Candidates", name="Scan Candidates", node_type=ProceduralNodeType.ACTION, description="Scan raw chapter text for candidate entities and terms."))
    g.add_node(ProceduralNode(id="Filter_Known", name="Filter Known Entities", node_type=ProceduralNodeType.VERIFICATION, description="Compare against known characters and glossary."))
    g.add_node(ProceduralNode(id="Deduce_Profiles", name="Deduce Character Profiles", node_type=ProceduralNodeType.ACTION, description="Infer gender, role, and speech quirks."))
    g.add_node(ProceduralNode(id="Prune_Trivial_Terms", name="Prune Trivial Terms", node_type=ProceduralNodeType.VERIFICATION, description="Prune common vocabulary, adjectives, and verbs."))

    # Edges
    g.add_edge(ProceduralEdge(
        source="Scan_Candidates",
        target="Filter_Known",
        condition="Entities found in text",
        guidance="Cross-reference candidate characters and terms against Known Characters and Glossary. Exclude already-registered entities.",
        pitfalls="Do NOT re-register existing characters under aliases or slight name variations."
    ))
    g.add_edge(ProceduralEdge(
        source="Filter_Known",
        target="Deduce_Profiles",
        condition="New character confirmed",
        guidance="Infer gender, role, and speaking style from dialogue particles, honorific suffixes, and contextual actions.",
        pitfalls="Never guess character gender blindly without textual clues; use neutral or unknown if ambiguous."
    ))
    g.add_edge(ProceduralEdge(
        source="Deduce_Profiles",
        target="Prune_Trivial_Terms",
        condition="New terminology candidate",
        guidance="Extract only domain-specific worldbuilding terms: martial ranks, magical techniques, factions, artifacts, and unique realm concepts.",
        pitfalls="CRITICAL: Do NOT extract everyday words, verbs, common adjectives, greetings, or generic titles. This wastes memory and output tokens."
    ))
    return g


def get_default_drafter_graph() -> ProceduralGraph:
    """Returns the default Procedural Graph for Novelistic Translation Drafting."""
    g = ProceduralGraph(
        graph_id="drafter_default_v1",
        description="Procedural execution graph for context-aware novelistic translation drafting."
    )
    # Nodes
    g.add_node(ProceduralNode(id="Scene_Init", name="Scene Initialization", node_type=ProceduralNodeType.ACTION, description="Establish scene setting and POV for initial chunk."))
    g.add_node(ProceduralNode(id="Boundary_Continuity", name="Boundary Continuity", node_type=ProceduralNodeType.ACTION, description="Seamlessly continue narrative flow from preceding chunk."))
    g.add_node(ProceduralNode(id="Zero_Anaphora_Resolution", name="Zero-Anaphora Resolution", node_type=ProceduralNodeType.ACTION, description="Resolve omitted subjects and pronouns."))
    g.add_node(ProceduralNode(id="Voice_Modulation", name="Voice Modulation", node_type=ProceduralNodeType.ACTION, description="Apply registered character voice and speech register."))
    g.add_node(ProceduralNode(id="Glossary_Lock", name="Glossary Lock", node_type=ProceduralNodeType.VERIFICATION, description="Enforce exact canonical terminology."))

    # Edges
    g.add_edge(ProceduralEdge(
        source="Scene_Init",
        target="Zero_Anaphora_Resolution",
        condition="First chunk or single chapter",
        guidance="Anchor character POV, establish narrative tense, and trace all omitted subjects from opening lines.",
        pitfalls="Do NOT generate introductory commentary, translation notes, or conversational filler."
    ))
    g.add_edge(ProceduralEdge(
        source="Boundary_Continuity",
        target="Zero_Anaphora_Resolution",
        condition="Chunk index > 1 with preceding context",
        guidance="Read Preceding Scene Context to identify the active speaker and ongoing sentence flow. Resume translating immediately.",
        pitfalls="CRITICAL: DO NOT repeat or re-translate preceding text. DO NOT restart the scene or re-introduce known characters."
    ))
    g.add_edge(ProceduralEdge(
        source="Zero_Anaphora_Resolution",
        target="Voice_Modulation",
        condition="Omitted subject in dialogue or narrative",
        guidance="Supply accurate target language pronouns by tracking who is speaking and acting using speech registers and honorifics.",
        pitfalls="Never guess speaker attributions; trace dialogue turn-taking carefully."
    ))
    g.add_edge(ProceduralEdge(
        source="Voice_Modulation",
        target="Glossary_Lock",
        condition="Character dialogue or domain terms present",
        guidance="Match dialogue tone to character voice profile. Enforce exact canonical glossary targets.",
        pitfalls="Do NOT flatten noble or formal registers into casual slang. Do NOT substitute synonyms for registered glossary terms."
    ))
    return g
