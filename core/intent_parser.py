"""
Intent Parser — Convert LLM JSON output to typed NodeGraph.

This replaces the brittle JSON blob with a structured, validated, auditable graph.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.node_graph import (
    Node, NodeType, NodeMetadata, TypedInterface, TypeSchema,
    NodeGraph, Coordinator
)
from core.models import AgentIntent


class IntentParser:
    """Parse LLM JSON output into a typed NodeGraph."""
    
    def __init__(self, agent_id: str = "general"):
        self.agent_id = agent_id
    
    def parse(self, llm_response: Dict[str, Any], prompt: str = "") -> NodeGraph:
        """Convert LLM JSON response to NodeGraph.
        
        The LLM outputs JSON like:
        {
            "reasoning": "...",
            "target_cell": "B2",  # single write
            "values": [[...]],    # 2D array
            # OR
            "intents": [          # multi-rectangle
                {"target_cell": "B2", "values": [[...]]},
                {"target_cell": "B10", "values": [[...]]}
            ],
            "chart_spec": {...},
            "macro_spec": {...},
            "plan": {...}
        }
        
        We convert this to a NodeGraph with:
        - RANGE_WRITE nodes for each intent
        - FORMULA nodes for formula cells
        - GROUP nodes to contain related writes
        - Metadata for audit trail
        """
        graph = NodeGraph()
        
        # Compute source intent hash for audit trail
        response_json = json.dumps(llm_response, sort_keys=True)
        intent_hash = hashlib.sha256(response_json.encode()).hexdigest()[:16]
        
        metadata = NodeMetadata(
            source_intent_hash=intent_hash,
            timestamp=datetime.now(timezone.utc),
            agent_id=self.agent_id,
            confidence=llm_response.get("confidence", 1.0),
            prompt=prompt[:500]  # Truncate for metadata
        )
        
        # Parse multi-intents or single intent
        intents = llm_response.get("intents")
        if intents and isinstance(intents, list):
            # Multi-rectangle write
            root = self._parse_multi_intents(intents, metadata)
        else:
            # Single rectangle write
            target = llm_response.get("target_cell", "A1")
            values = llm_response.get("values", [])
            root = self._parse_single_intent(target, values, metadata)
        
        graph.root = root
        graph._index_node(root)
        
        return graph
    
    def _parse_multi_intents(
        self, 
        intents: List[Dict[str, Any]], 
        metadata: NodeMetadata
    ) -> Node:
        """Parse a list of intent rectangles into a GROUP node."""
        group = Node(
            id=f"group_{metadata.source_intent_hash}",
            node_type=NodeType.GROUP,
            interface=TypedInterface(
                inputs={},
                outputs={"result": TypeSchema.string()}
            ),
            metadata=metadata
        )
        
        for i, intent in enumerate(intents):
            target = intent.get("target_cell", "A1")
            values = intent.get("values", [])
            
            child = self._parse_single_intent(
                target, values, 
                metadata, 
                node_id=f"range_{i}_{metadata.source_intent_hash[:8]}"
            )
            group.children.append(child)
        
        return group
    
    def _parse_single_intent(
        self,
        target_cell: str,
        values: List[List[Any]],
        metadata: NodeMetadata,
        node_id: Optional[str] = None
    ) -> Node:
        """Parse a single intent (target cell + 2D values) into a RANGE_WRITE node.
        
        The values array is a 2D list. Each cell may be:
        - A static value (number, string, bool)
        - A formula string starting with "="
        - Empty/null
        
        We create:
        - One RANGE_WRITE node for the overall write
        - Child FORMULA nodes for any cells containing formulas
        """
        if node_id is None:
            node_id = f"range_{metadata.source_intent_hash[:8]}"
        
        # Create the main RANGE_WRITE node
        range_node = Node(
            id=node_id,
            node_type=NodeType.RANGE_WRITE,
            interface=TypedInterface(
                inputs={
                    "start_cell": TypeSchema.cell_ref(),
                    "values": TypeSchema.list(TypeSchema.any())
                },
                outputs={"result": TypeSchema.string()}
            ),
            inputs={
                "start_cell": target_cell,
                "values": values
            },
            metadata=metadata
        )
        
        # Parse values to detect formulas
        if values and isinstance(values, list):
            for row_idx, row in enumerate(values):
                if not isinstance(row, list):
                    continue
                for col_idx, cell_value in enumerate(row):
                    if isinstance(cell_value, str) and cell_value.startswith("="):
                        # This cell contains a formula
                        formula_node = self._create_formula_node(
                            target_cell, row_idx, col_idx,
                            cell_value, metadata, node_id
                        )
                        range_node.children.append(formula_node)
        
        return range_node
    
    def _create_formula_node(
        self,
        range_target: str,
        row_offset: int,
        col_offset: int,
        formula: str,
        metadata: NodeMetadata,
        parent_id: str
    ) -> Node:
        """Create a FORMULA node for a cell containing a formula."""
        # Compute the actual cell reference
        from core.utils import a1_to_coords, coords_to_a1
        
        try:
            start_row, start_col = a1_to_coords(range_target)
            actual_row = start_row + row_offset
            actual_col = start_col + col_offset
            cell_ref = coords_to_a1(actual_row, actual_col)
        except Exception:
            cell_ref = f"{range_target}+{row_offset},{col_offset}"
        
        # Parse formula to extract function name and args
        # Simple parsing: =FUNCTION(arg1, arg2, ...)
        formula_clean = formula[1:] if formula.startswith("=") else formula
        
        return Node(
            id=f"formula_{parent_id}_{row_offset}_{col_offset}",
            node_type=NodeType.FORMULA,
            interface=TypedInterface(
                inputs={
                    "cell": TypeSchema.cell_ref(),
                    "formula": TypeSchema.string(),
                    "args": TypeSchema.list(TypeSchema.any(), optional=True)
                },
                outputs={"result": TypeSchema.number(optional=True)}
            ),
            inputs={
                "cell": cell_ref,
                "formula": formula_clean,
                "args": []  # Will be populated by Coordinator
            },
            metadata=metadata
        )
    
    def to_agent_intents(self, graph: NodeGraph) -> List[AgentIntent]:
        """Convert a NodeGraph to a list of AgentIntents for the existing kernel.
        
        This bridges the new node graph system with the existing kernel.
        """
        intents = []
        
        def collect_range_writes(node: Node) -> None:
            """Recursively collect RANGE_WRITE nodes."""
            if node.node_type == NodeType.RANGE_WRITE:
                values = node.inputs.get("values", [])
                target = node.inputs.get("start_cell", "A1")
                shift = node.inputs.get("shift_direction", "right")
                
                if values:
                    intent = AgentIntent(
                        agent_id=node.metadata.agent_id if node.metadata else "general",
                        target_start_a1=target,
                        data_payload=values,
                        shift_direction=shift
                    )
                    intents.append(intent)
            
            for child in node.children:
                collect_range_writes(child)
        
        if graph.root:
            collect_range_writes(graph.root)
        
        return intents


def create_query_node(cell_ref: str, metadata: NodeMetadata) -> Node:
    """Create a node that queries the kernel for cell value/lock status."""
    return Node(
        id=f"query_{metadata.source_intent_hash}_{cell_ref}",
        node_type=NodeType.QUERY,
        interface=TypedInterface(
            inputs={"cell": TypeSchema.cell_ref()},
            outputs={
                "value": TypeSchema.any(optional=True),
                "locked": TypeSchema.boolean(),
                "formula": TypeSchema.string(optional=True)
            }
        ),
        inputs={"cell": cell_ref},
        metadata=metadata
    )


def validate_with_feedback(
    graph: NodeGraph,
    coordinator: Coordinator
) -> Tuple[bool, List[str]]:
    """Validate a graph and return feedback for the LLM to self-correct.
    
    Returns (is_valid, list_of_error_messages).
    The LLM can use these messages to generate a corrected intent.
    """
    errors = graph.validate()
    
    if errors:
        return False, errors
    
    # Check for collisions
    collisions = coordinator.detect_collisions(graph)
    if collisions:
        for coll in collisions:
            errors.append(
                f"Collision: cell {coll['cell']} is written by multiple nodes: "
                f"{', '.join(coll['nodes'])}"
            )
    
    # Check for locks would go here
    # locked = coordinator.check_locks(graph)
    
    return len(errors) == 0, errors
