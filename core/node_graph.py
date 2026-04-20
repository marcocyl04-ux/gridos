"""
Node Graph — typed, composable intermediate layer between LLM and kernel.

Inspired by Weft's design patterns:
- Typed interfaces (nodes declare input/output types)
- Recursive composability (nodes contain nodes)
- Null propagation (failures cascade gracefully)
- Coordination vs. computation separation

The node graph sits between the LLM's JSON output and the kernel's write operations.
It validates, composes, and produces an audit trail before anything touches the grid.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


class NodeType(Enum):
    """Types of nodes in the graph."""
    CELL_WRITE = auto()      # Write a single cell value
    RANGE_WRITE = auto()     # Write a 2D range of values
    FORMULA = auto()         # Formula evaluation
    CONDITIONAL = auto()     # Conditional branch
    AGGREGATE = auto()       # Aggregate function (SUM, AVERAGE, etc.)
    QUERY = auto()           # Query kernel state (read-only)
    GROUP = auto()           # Container for other nodes (recursive)


@dataclass(frozen=True)
class TypeSchema:
    """Type schema for node interfaces."""
    name: str
    optional: bool = False
    
    @staticmethod
    def number(optional: bool = False) -> TypeSchema:
        return TypeSchema("number", optional)
    
    @staticmethod
    def string(optional: bool = False) -> TypeSchema:
        return TypeSchema("string", optional)
    
    @staticmethod
    def boolean(optional: bool = False) -> TypeSchema:
        return TypeSchema("boolean", optional)
    
    @staticmethod
    def cell_ref(optional: bool = False) -> TypeSchema:
        return TypeSchema("cell_ref", optional)
    
    @staticmethod
    def range_ref(optional: bool = False) -> TypeSchema:
        return TypeSchema("range_ref", optional)
    
    @staticmethod
    def any(optional: bool = False) -> "TypeSchema":
        return TypeSchema("any", optional)
    
    @staticmethod
    def list(inner: TypeSchema, optional: bool = False) -> "ListTypeSchema":
        return ListTypeSchema(inner, optional)


@dataclass(frozen=True)
class ListTypeSchema(TypeSchema):
    """List type with inner element type."""
    inner: TypeSchema = field(default_factory=lambda: TypeSchema("any"))
    
    def __init__(self, inner: TypeSchema, optional: bool = False):
        object.__setattr__(self, "name", f"list[{inner.name}]")
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "optional", optional)


@dataclass(frozen=True)
class TypedInterface:
    """Every node declares its input/output types explicitly."""
    inputs: Dict[str, TypeSchema]
    outputs: Dict[str, TypeSchema]
    null_propagation: bool = True  # If true, null inputs → null outputs


@dataclass(frozen=True)
class NodeMetadata:
    """Audit metadata for every node."""
    source_intent_hash: str  # Hash of the LLM intent that produced this node
    timestamp: datetime
    agent_id: str
    confidence: float = 1.0  # LLM confidence score (0-1)
    prompt: str = ""  # The prompt that generated this node


@dataclass
class Node:
    """A node in the computation graph."""
    id: str
    node_type: NodeType
    interface: TypedInterface
    
    # Node value/state
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # Recursive composability: nodes can contain nodes
    children: List[Node] = field(default_factory=list)
    
    # Audit trail
    metadata: Optional[NodeMetadata] = None
    
    # Evaluation state
    _evaluated: bool = field(default=False, repr=False)
    _nullified: bool = field(default=False, repr=False)
    _error: Optional[str] = field(default=None, repr=False)
    
    def is_leaf(self) -> bool:
        """A leaf node has no children."""
        return len(self.children) == 0
    
    def is_group(self) -> bool:
        """A group node contains other nodes."""
        return self.node_type == NodeType.GROUP
    
    def get_all_descendants(self) -> List[Node]:
        """Get all descendant nodes (recursive)."""
        result = []
        for child in self.children:
            result.append(child)
            result.extend(child.get_all_descendants())
        return result


class TypeChecker:
    """Validates that values match type schemas."""
    
    @staticmethod
    def check(value: Any, schema: TypeSchema) -> Tuple[bool, Optional[str]]:
        """Check if a value matches a type schema. Returns (valid, error_message)."""
        if value is None:
            if schema.optional:
                return True, None
            return False, f"Required field cannot be null"
        
        if isinstance(schema, ListTypeSchema):
            if not isinstance(value, list):
                return False, f"Expected list, got {type(value).__name__}"
            for i, item in enumerate(value):
                valid, error = TypeChecker.check(item, schema.inner)
                if not valid:
                    return False, f"List item {i}: {error}"
            return True, None
        
        type_checks = {
            "number": (int, float),
            "string": str,
            "boolean": bool,
            "cell_ref": str,  # A1 notation
            "range_ref": str,  # A1:B5 notation
            "any": object,
        }
        
        expected = type_checks.get(schema.name)
        if expected is None:
            return False, f"Unknown type: {schema.name}"
        
        if isinstance(expected, tuple):
            if not isinstance(value, expected):
                return False, f"Expected {schema.name}, got {type(value).__name__}"
        else:
            if not isinstance(value, expected):
                return False, f"Expected {schema.name}, got {type(value).__name__}"
        
        return True, None


class NodeGraph:
    """The intermediate layer between LLM and kernel.
    
    A graph is a collection of nodes with connections between them.
    The graph validates types before execution and propagates nulls gracefully.
    """
    
    def __init__(self, root: Optional[Node] = None):
        self.root = root
        self.nodes: Dict[str, Node] = {}
        self.connections: Dict[str, List[str]] = {}  # node_id -> [downstream_node_ids]
        self.errors: List[str] = []
        
        if root:
            self._index_node(root)
    
    def _index_node(self, node: Node) -> None:
        """Add a node and its descendants to the index."""
        self.nodes[node.id] = node
        for child in node.children:
            self._index_node(child)
    
    def add_node(self, node: Node, parent_id: Optional[str] = None) -> None:
        """Add a node to the graph. Optionally attach to a parent group."""
        self.nodes[node.id] = node
        
        if parent_id:
            parent = self.nodes.get(parent_id)
            if parent and parent.is_group():
                parent.children.append(node)
    
    def connect(self, from_id: str, to_id: str) -> None:
        """Connect two nodes: from -> to."""
        if from_id not in self.connections:
            self.connections[from_id] = []
        self.connections[from_id].append(to_id)
    
    def validate(self) -> List[str]:
        """Type-check every node against its interface. Returns list of errors."""
        errors = []
        
        for node_id, node in self.nodes.items():
            # Check inputs
            for input_name, input_schema in node.interface.inputs.items():
                value = node.inputs.get(input_name)
                valid, error = TypeChecker.check(value, input_schema)
                if not valid:
                    errors.append(f"Node {node_id}.{input_name}: {error}")
            
            # Check connections for type compatibility
            if node_id in self.connections:
                for downstream_id in self.connections[node_id]:
                    downstream = self.nodes.get(downstream_id)
                    if not downstream:
                        errors.append(f"Node {node_id} connects to unknown node {downstream_id}")
                        continue
                    
                    # For now, simple check: output names must match downstream input names
                    # Real implementation would match specific output->input mappings
                    for output_name in node.interface.outputs:
                        if output_name not in downstream.interface.inputs:
                            errors.append(
                                f"Type mismatch: {node_id}.{output_name} -> {downstream_id} "
                                f"(no matching input)"
                            )
        
        self.errors = errors
        return errors
    
    def propagate_nulls(self) -> Set[str]:
        """Propagate null values through the graph.
        
        If a node with null_propagation=True receives null inputs, 
        it outputs null and its downstream nodes are also nullified.
        """
        nullified = set()
        
        def visit(node: Node) -> bool:
            """Visit a node, return True if it outputs null."""
            if node.id in nullified:
                return True
            
            # Check if any inputs are null
            has_null_input = any(v is None for v in node.inputs.values())
            
            if has_null_input and node.interface.null_propagation:
                nullified.add(node.id)
                node._nullified = True
                return True
            
            return False
        
        # Visit all nodes
        for node in self.nodes.values():
            visit(node)
        
        return nullified
    
    def to_execution_order(self) -> List[Node]:
        """Topological sort of nodes for execution."""
        # Simple approach: groups first, then leaves
        # Real implementation would do proper dependency analysis
        groups = [n for n in self.nodes.values() if n.is_group()]
        leaves = [n for n in self.nodes.values() if n.is_leaf()]
        return groups + leaves
    
    def to_audit_log(self) -> Dict[str, Any]:
        """Produce a full audit trail of the graph."""
        return {
            "version": "1.0",
            "node_count": len(self.nodes),
            "validation_errors": self.errors,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type.name,
                    "inputs": {k: str(v)[:100] for k, v in n.inputs.items()},
                    "outputs": {k: str(v)[:100] for k, v in n.outputs.items()},
                    "metadata": {
                        "source_intent_hash": n.metadata.source_intent_hash if n.metadata else None,
                        "timestamp": n.metadata.timestamp.isoformat() if n.metadata else None,
                        "agent_id": n.metadata.agent_id if n.metadata else None,
                        "confidence": n.metadata.confidence if n.metadata else None,
                    },
                    "nullified": n._nullified,
                    "error": n._error,
                    "child_count": len(n.children),
                }
                for n in self.nodes.values()
            ]
        }
    
    def to_json(self) -> str:
        """Serialize graph to JSON."""
        return json.dumps(self.to_audit_log(), indent=2)


class Coordinator:
    """Handles ordering, collision detection, lock checking.
    
    The Coordinator is responsible for the 'what' and 'where' of writes,
    but not the 'how'. It validates that writes are safe and ordered correctly.
    """
    
    def __init__(self, kernel: Any):
        self.kernel = kernel  # GridOSKernel instance
    
    def plan_execution(self, graph: NodeGraph) -> List[Node]:
        """Create an execution plan from a validated graph.
        
        Returns nodes in the order they should be executed.
        """
        errors = graph.validate()
        if errors:
            raise ValueError(f"Graph validation failed: {errors}")
        
        order = graph.to_execution_order()
        
        # Filter out nullified nodes
        order = [n for n in order if not n._nullified]
        
        return order
    
    def detect_collisions(self, graph: NodeGraph) -> List[Dict[str, Any]]:
        """Detect if multiple nodes write to the same cell."""
        cell_writes: Dict[str, List[str]] = {}  # cell -> [node_ids]
        
        for node in graph.nodes.values():
            if node.node_type == NodeType.CELL_WRITE:
                cell = node.inputs.get("cell")
                if cell:
                    if cell not in cell_writes:
                        cell_writes[cell] = []
                    cell_writes[cell].append(node.id)
            
            elif node.node_type == NodeType.RANGE_WRITE:
                # For ranges, we'd need to expand the range to individual cells
                # For now, just check the start cell
                start = node.inputs.get("start_cell")
                if start:
                    if start not in cell_writes:
                        cell_writes[start] = []
                    cell_writes[start].append(node.id)
        
        collisions = [
            {"cell": cell, "nodes": nodes}
            for cell, nodes in cell_writes.items()
            if len(nodes) > 1
        ]
        
        return collisions
    
    def check_locks(self, graph: NodeGraph) -> List[Dict[str, Any]]:
        """Check if any write targets are locked cells."""
        locked = []
        
        for node in graph.nodes.values():
            if node.node_type in (NodeType.CELL_WRITE, NodeType.RANGE_WRITE):
                # Query kernel for lock status
                # This is a simplified version - real implementation would check properly
                pass  # TODO: implement when kernel interface is ready
        
        return locked


class Executor:
    """Pure computation. Takes a node, returns a value.
    
    The Executor handles formula evaluation, data transforms, and computation.
    It does NOT touch locks, ordering, or coordination — that's the Coordinator's job.
    """
    
    def __init__(self, formula_registry: Dict[str, Callable]):
        self.formula_registry = formula_registry
    
    def evaluate(self, node: Node, resolved_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a node given its resolved inputs."""
        if node._nullified:
            return {k: None for k in node.interface.outputs}
        
        try:
            if node.node_type == NodeType.FORMULA:
                return self._eval_formula(node, resolved_inputs)
            elif node.node_type == NodeType.AGGREGATE:
                return self._eval_aggregate(node, resolved_inputs)
            elif node.node_type == NodeType.CELL_WRITE:
                return {"result": resolved_inputs.get("value")}
            elif node.node_type == NodeType.RANGE_WRITE:
                return {"result": resolved_inputs.get("values")}
            else:
                return {k: resolved_inputs.get(k) for k in node.interface.outputs}
        
        except Exception as e:
            node._error = str(e)
            return {k: None for k in node.interface.outputs}
    
    def _eval_formula(self, node: Node, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a formula node."""
        formula_def = inputs.get("formula")
        args = inputs.get("args", [])
        
        # Look up formula in registry
        if isinstance(formula_def, str) and formula_def.upper() in self.formula_registry:
            func = self.formula_registry[formula_def.upper()]
            result = func(*args)
            return {"result": result}
        
        return {"result": None, "error": f"Unknown formula: {formula_def}"}
    
    def _eval_aggregate(self, node: Node, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an aggregate node (SUM, AVERAGE, etc.)."""
        values = inputs.get("values", [])
        operation = inputs.get("operation", "SUM")
        
        if not values:
            return {"result": 0}
        
        if operation == "SUM":
            return {"result": sum(values)}
        elif operation == "AVERAGE":
            return {"result": sum(values) / len(values)}
        elif operation == "MAX":
            return {"result": max(values)}
        elif operation == "MIN":
            return {"result": min(values)}
        else:
            return {"result": None, "error": f"Unknown aggregate operation: {operation}"}
