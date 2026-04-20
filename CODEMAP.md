# GridOS Code Navigation Map

Quick reference for navigating the main codebase without restructuring.

## main.py Structure

### Global Setup (Lines 1-200)
- Imports and configuration
- `app = FastAPI()` - App instance
- Rate limiting middleware
- Static file mounting

### Core Objects (Lines 200-400)
- `kernel = GridOSKernel()` - THE main spreadsheet engine
- `AGENTS = load_agents()` - Loaded agent definitions
- `providers` - LLM provider instances

---

## Key Route Sections

### Agent Routes (Lines 400-800)
**File Search: `/agent/chat` or `generate_agent_preview`**

```python
@app.post("/agent/chat")
def generate_agent_preview(req: ChatRequest)
```
- Takes user prompt → calls `route_prompt()` → picks agent
- Builds system instruction with `build_system_instruction()`
- Calls LLM → parses response → returns preview (no write yet)

**File Search: `/agent/apply`**
```python
@app.post("/agent/apply")
async def apply_agent_suggestion(req: ApplyRequest)
```
- Actually applies the preview to grid
- Calls `kernel.process_agent_intent()`
- Returns success/collision info

**File Search: `/agent/execute-graph` or `execute_node_graph`**
```python
@app.post("/agent/execute-graph")
async def execute_node_graph(req: ExecuteGraphRequest)
```
- Takes node graph JSON
- Creates `Coordinator` instance
- Executes graph → returns results
- **BUT**: Currently returns hardcoded example (see line ~1050)
- **TODO**: Wire this up to actual graph execution

---

### Grid Routes (Lines 800-1100)
**File Search: `/grid/cell`**
```python
@app.post("/grid/cell")
async def grid_cell(req: CellRequest)
```
- Direct cell writes
- Calls `kernel.write_cell()` or `kernel.write_cell_expr()`

**File Search: `/grid/range`**
```python
@app.post("/grid/range")
async def grid_range(req: RangeRequest)
```
- Range writes
- Calls `kernel.write_range()`

**File Search: `/system/load` or `/system/save`**
```python
@app.get("/system/load")
async def system_load()

@app.post("/system/save")
async def system_save(req: SaveRequest)
```
- Load/save workbook state
- Returns full grid JSON

---

### Template Routes (Lines 1100-1400)
**File Search: `/templates/available`**
```python
@app.get("/templates/available")
async def templates_available()
```
- Returns JSON list of YAML templates
- Checks `assets/templates/` directory

**File Search: `/templates/apply` or `apply_template`**
```python
@app.post("/templates/apply/{template_id}")
async def apply_template(template_id: str, req: ApplyTemplateRequest)
```
- Loads YAML template
- Renders with `render_yaml_template()`
- Applies respecting locks with `apply_template_respecting_locks()`

---

### System Routes (Lines 1400-1600)
**File Search: `/healthz`**
```python
@app.get("/healthz")
async def health_check()
```
- Simple health check

**File Search: `/auth/whoami` or `/cloud/status`**
- Auth-related endpoints
- Returns user info and SaaS config

---

## Critical Kernel Methods

The `kernel` object (GridOSKernel) is THE interface to the spreadsheet.

Search for these calls in main.py:

### Read Operations
- `kernel.get_cells(range_str)` - Get cell values
- `kernel._sheet_state(sheet_name)` - Get full sheet state
- `kernel.get_context_for_ai(...)` - Build context for LLM
- `kernel.preview_agent_intent(intent, sheet)` - Preview writes

### Write Operations
- `kernel.write_cell(cell, value, sheet)` - Write single cell
- `kernel.write_cell_expr(cell, formula, sheet)` - Write formula
- `kernel.write_range(start, values, sheet)` - Write range
- `kernel.process_agent_intent(intent, sheet)` - Apply agent suggestion

### State Management
- `kernel.load(data)` - Load full workbook
- `kernel.save()` - Save current state
- `kernel.clear(sheet)` - Clear sheet

---

## Quick Function Reference

### Route Prompt Classification
**Search: `def route_prompt`**
- Classifies user intent
- Returns agent ID ("write", "chart", "macro", "sheet", "suggest")

### Build System Prompt
**Search: `def build_system_instruction`**
- Creates system prompt for LLM
- Includes context about locked cells, existing data
- Output format spec

### Parse AI Response
**Search: `def _parse_ai_response`**
- Parses LLM JSON output
- Validates structure
- Returns dict with values/target_cell/intents

---

## Node Graph (Currently Underutilized)

The node graph system exists but isn't fully wired:

**Search: `core/node_graph.py`**
- `NodeGraph` class - builds computation graphs
- `Node` class - individual operations
- `Coordinator` - executes graphs
- `Executor` - runs individual nodes

**Current State in main.py:**
- Search `"execute-graph"` or `execute_node_graph`
- Currently returns hardcoded example response
- **Opportunity**: Wire up to actually execute node graphs

---

## Provider System

**Search: `core/providers.py`**

Multi-LLM provider interface:
- `OpenRouterProvider`
- `AnthropicProvider`
- `GeminiProvider`
- `GroqProvider`

Used in main.py via:
- `call_model(agent_id, ...)` - Primary LLM call
- `_providers_for_current_request()` - Get available providers

---

## File Organization

```
main.py              # All routes + business logic
├── Global setup
├── App instance
├── Middleware
├── AGENTS load
├── Kernel init
├── Agent routes        ~400-800 lines
├── Grid routes         ~800-1100 lines
├── Template routes     ~1100-1400 lines
├── Formula routes      ~1400-1600 lines
├── Import routes       ~1600-1800 lines
├── Auth/Cloud routes   ~1800-2000 lines
├── Static routes       ~2000-2200 lines
└── Helper functions    ~2200-3000+ lines

core/
├── engine.py          # GridOSKernel (grid operations)
├── node_graph.py      # Node graph system
├── intent_parser.py   # Intent → node conversion
├── declarative_plugins.py  # YAML templates
├── providers.py       # LLM provider abstractions
└── functions.py       # Formula evaluator

agents/
└── agents.yaml        # Agent definitions

assets/templates/      # YAML financial templates
*.yaml                 # DCF, LBO, Comps, etc.

static/                # Frontend
├── index.html         # Main workbook UI
├── app.js             # Frontend logic
└── dev/               # DevTools (NEW)
    ├── index.html
    └── dev.js
```

---

## Common Tasks

### "Where do I look for..."

**Agent writing to grid?**
→ `/agent/apply` route, calls `kernel.process_agent_intent()`

**Template application?**
→ `/templates/apply/{id}` route, uses `render_yaml_template()`

**Formula evaluation?**
→ `core/functions.py` - `FormulaEvaluator` class

**Node graph execution?**
→ `/agent/execute-graph` route (currently stub)
→ `core/node_graph.py` - actual implementation ready

**LLM provider selection?**
→ `call_model()` function
→ `_pick_router_model()` for agent routing

**Authentication?**
→ `/auth/*` routes
→ Supabase integration in cloud setup

---

## For Modification

### Add new endpoint
```python
@app.post("/my/new/endpoint")
async def my_new_endpoint(req: MyRequest):
    # Business logic here
    return {"status": "ok"}
```

### Add helper function
- Put after existing helper functions (~line 2200+)
- Or create in `core/some_module.py` and import

### Modify agent behavior
- Edit `agents/agents.yaml` for agent definitions
- Edit `BASE_SYSTEM_RULES` for base instructions
- Edit `generate_agent_preview()` for generation logic

---

## Testing Tips

```bash
# Run locally
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Test specific endpoint
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Set A1 to 100"}'

# See integration tests
cat test_integration.py
```

---

## Summary

**Core Principle**: `kernel` is the spreadsheet. Everything routes through it.

**Agent Flow**:
1. `/agent/chat` → `route_prompt()` → `build_system_instruction()` → `call_model()`
2. Parse response → return preview
3. `/agent/apply` → `kernel.process_agent_intent()` → Cells updated

**Template Flow**:
1. `/templates/apply/{id}` → `render_yaml_template()`
2. `apply_template_respecting_locks()` → Cells updated

**Graph Flow** (Currently minimal):
1. `/agent/execute-graph` → (stub)
2. **Opportunity**: Wire to `NodeGraph` + `Coordinator`
