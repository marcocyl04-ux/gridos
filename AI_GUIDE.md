# GridOS AI Developer Guide

This guide helps AI agents understand and work with the GridOS codebase effectively.

## Quick Navigation

```
/tmp/gridos-rebuild/
├── main.py                 # FastAPI app, all HTTP routes
├── core/
│   ├── node_graph.py       # Node graph system (NodeGraph, Node, NodeType)
│   ├── intent_parser.py    # Parses LLM output to node graphs
│   ├── declarative_plugins.py  # YAML templates, formulas
│   ├── engine.py           # GridOSKernel (grid operations)
│   ├── providers.py        # LLM provider abstractions
│   └── models.py           # Pydantic models
├── static/
│   ├── index.html          # Main workbook UI (SD's original)
│   ├── app.js              # Frontend logic
│   └── dev/                # DevTools interface (NEW)
│       ├── index.html
│       └── dev.js
└── assets/templates/       # YAML financial templates
```

## Key Endpoints for AI Manipulation

### Agent Chat
```
POST /agent/chat
{
  "workbook_id": "uuid",
  "agent_id": "default",
  "message": "Calculate DCF for Apple with 5% growth"
}
```

### Execute Node Graph
```
POST /agent/execute-graph
{
  "nodes": [
    {
      "id": "n1",
      "node_type": "QUERY",
      "interface": { "inputs": {}, "outputs": {} },
      "inputs": { "range": "A1:A10" }
    }
  ],
  "connections": []
}
```

### Apply Template
```
POST /templates/apply/{template_id}
{
  "variables": {
    "company_name": "Acme Corp",
    "growth_rate": 0.05
  }
}
```

## Node Types

| Type | Purpose | Color (UI) |
|------|---------|------------|
| `CELL_WRITE` | Write to single cell | Green |
| `RANGE_WRITE` | Write to range | Green |
| `FORMULA` | Compute formula | Orange |
| `CONDITIONAL` | If/then branch | Purple |
| `AGGREGATE` | SUM, AVG, etc | Orange |
| `QUERY` | Read from grid | Blue |
| `GROUP` | Container nodes | Gray |

## Node Graph System

Nodes are typed with explicit interfaces:

```python
from core.node_graph import NodeGraph, Node, NodeType, TypedInterface, TypeSchema

# Create a graph
graph = NodeGraph()

# Add a query node
query_node = Node(
    id="get_revenue",
    node_type=NodeType.QUERY,
    interface=TypedInterface(
        inputs={"range": TypeSchema.range_ref()},
        outputs={"values": TypeSchema.list(TypeSchema.number())}
    ),
    inputs={"range": "A1:A12"}
)
graph.add_node(query_node)

# Add a formula node
formula_node = Node(
    id="calc_growth",
    node_type=NodeType.FORMULA,
    interface=TypedInterface(
        inputs={"values": TypeSchema.list(TypeSchema.number())},
        outputs={"result": TypeSchema.number()}
    ),
    inputs={"formula": "=(B2-B1)/B1"}
)
graph.add_node(formula_node)

# Connect them
graph.connect("get_revenue", "calc_growth", "values")

# Validate
errors = graph.validate()
if errors:
    print("Validation errors:", errors)
```

## Intent Parser

Converts natural language to node graphs:

```python
from core.intent_parser import IntentParser

parser = IntentParser()
intent = parser.parse("Set A1 to 100 and calculate sum in B1")
# Returns AgentIntent with nodes for the operations
```

## YAML Templates

Templates define reusable financial models:

```yaml
name: DCF Valuation
sheet_name: DCF Model
formulas:
  - cell: B2
    formula: "100000"  # Revenue
    style:
      number_format: currency
  - cell: B5
    formula: "=B2*0.05"  # Growth
sections:
  - name: Assumptions
    cells:
      - ref: A1
        value: Growth Rate
      - ref: B1
        value: 0.05
```

Apply via: `POST /templates/apply/dcf_valuation`

## DevTools Interface

For visual graph editing and API exploration:

1. Open `/dev/` in browser
2. Use Node Graph panel to build graphs visually
3. Use API Explorer to test endpoints
4. Use Intent Playground to see how prompts parse

## Common Tasks

### Add a New Node Type
1. Add to `NodeType` enum in `core/node_graph.py`
2. Add color mapping in `static/dev/dev.js`
3. Add handler in `Executor.execute_node()`

### Add a New Formula Function
1. Add to `FormulaEvaluator` in `core/functions.py`
2. Or use declarative: add to `DEFAULT_MATH_REGISTRY` in `core/declarative_plugins.py`

### Add a New Template
1. Create YAML in `assets/templates/`
2. Follow naming: `{name}_template.yaml`
3. Restart server to load

### Debug Node Graph Execution
```python
# Enable verbose logging
graph.execute(verbose=True)

# Check audit trail
for node in graph.nodes:
    print(f"{node.id}: {node.outputs} (error: {node._error})")
```

## Testing

Run integration tests:
```bash
cd /tmp/gridos-rebuild
python -m pytest test_integration.py -v
```

## Provider System

Supports multiple LLM backends:
- OpenRouter (default)
- Anthropic (Claude)
- Google (Gemini)
- Groq

Configure via env vars or dashboard at `/dashboard`.

## Files to Read When Working On...

| Task | Key Files |
|------|-----------|
| Agent behavior | `main.py:/agent/*`, `core/intent_parser.py` |
| Grid operations | `core/engine.py:GridOSKernel` |
| Node graph | `core/node_graph.py` |
| UI changes | `static/app.js`, `static/index.html` |
| Templates | `core/declarative_plugins.py`, `assets/templates/*.yaml` |
| Auth | `main.py:/auth/*`, Supabase integration |

## Gotchas

1. **Always validate node graphs** before execution - types must match
2. **Nodes are immutable after creation** - use `_evaluated` flag to check state
3. **Null propagation** - if input is null and `null_propagation` is true, output is null
4. **Workbook scope** - always pass `workbook_id` in SaaS mode
5. **Templates deploy from `assets/` not `data/`** - `data/` is gitignored
