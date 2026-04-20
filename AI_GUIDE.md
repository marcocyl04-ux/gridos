# GridOS — AI Contributor Guide

## 1. What GridOS Is

GridOS is an agentic spreadsheet: a deterministic Python kernel manages cell state while an LLM interprets natural-language prompts and proposes structured write-intents. The kernel previews, collision-checks, and applies those intents so the AI can edit the sheet without clobbering locked or occupied cells.

## 2. Repo Map

```
main.py                  FastAPI entrypoint — mounts route modules, serves static pages
core/                    Kernel and API layer
  engine.py              GridOSKernel: cell state, recalculation, lock enforcement
  models.py              Pydantic schemas (AgentIntent, WriteResponse)
  functions.py           Formula registry (SUM, MAX, IF, …)
  macros.py              User-authored macros on top of primitives
  utils.py               A1-notation ↔ (row, col) conversion
  plugins.py             Plugin loader; PluginKernel facade (@kernel.formula, .agent, .model)
  declarative_plugins.py YAML template rendering and declarative formula registry
  import_engine.py       CSV/Excel import (reserved for upcoming feature)
  workbook_store.py      Persistence: FileWorkbookStore (OSS) / SupabaseWorkbookStore (SaaS)
  api/
    agents.py            /agent/chat, /agent/apply, /agent/write, /agent/chat/chain
    deps.py              Shared state: kernel pool, providers, macros, middleware, call_model()
    grid.py              /grid/cell read/write, sheet CRUD
    templates.py         /templates/apply/{id}
    workbooks.py         Save/load workbook state
    charts.py            Chart creation
    settings.py          /settings/providers, /settings/keys/*
    tools.py             /tools (hero tools)
    auth_usage.py        Auth middleware, /cloud/status, usage tracking
core/providers/          LLM provider abstraction
  base.py                Provider interface, error classifiers
  catalog.py             Static model catalog + fallback rules
  gemini.py / anthropic.py / groq.py / openrouter.py  Concrete providers
agents/                  Agent JSON configs (finance.json, general.json)
plugins/                 Drop-in extension packages (hello_world, black_scholes, real_estate)
cloud/                   SaaS tier (dormant unless SAAS_MODE=true): auth, storage, quotas
static/                  Frontend (vanilla JS + Tailwind)
  landing.html           Start-a-workbook page
  index.html             Main workbook UI
  app.js                 Workbook interactivity
  login.html / login.js  Auth pages (SaaS)
  dashboard.html         Workbook picker (SaaS)
data/                    YAML templates, persisted state
test_*.py                Offline tests (no server, no API calls)
```

## 3. Request Flow — Chat to Sheet

A typical cycle from user prompt to applied values:

1. **Landing page** (`static/landing.html`) → user describes what to build → POST to `/agent/chat`.
2. **`/agent/chat`** handler in `core/api/agents.py` → calls `generate_agent_preview(req)`.
3. **`generate_agent_preview()`** in `core/api/deps.py` (line ~1201):
   - Reads grid context via `kernel.get_context_for_ai()`.
   - Routes the prompt through `route_prompt()` to pick an agent (finance or general).
   - Builds a system instruction via `build_system_instruction()`.
   - Calls `call_model()` (line ~549) which resolves the model, calls the provider, and returns the response.
   - Parses the JSON response with `_parse_ai_response()`.
   - Creates an `AgentIntent` and calls `kernel.preview_agent_intent()` (in `core/engine.py`, line ~420) to generate a preview with collision detection.
   - Returns the preview (target cell, proposed values, any chart spec or macro proposal).
4. **Frontend** (`static/app.js`) renders the preview. User clicks Apply.
5. **`/agent/apply`** handler in `core/api/agents.py` → calls `kernel.process_agent_intent()` (in `core/engine.py`, line ~406) which writes values, recalculates formulas, and resolves collisions.
6. **`/agent/write`** is a direct-write path (no LLM) — same `kernel.process_agent_intent()` call.

## 4. Extension Seams

Three ways to extend GridOS, all via `plugins/`:

- **Formula** — `@kernel.formula("MY_FUNC")` on a Python callable registers a new spreadsheet function. See `plugins/README.md`.
- **Agent** — `kernel.agent({...})` registers a specialist agent with its own system prompt and JSON schema. See `plugins/README.md`.
- **Model** — `kernel.model({...})` adds an entry to the model catalog from a plugin. See `plugins/README.md`.

Plugins are auto-loaded on boot from `plugins/*/plugin.py` with `manifest.json` metadata.

## 5. Shared State

All shared state lives in `core/api/deps.py`:

- **`kernel`** — `GridOSKernel` instance (or kernel pool in SaaS mode via `_kernel_for_scope()` and `ContextVar`). Holds cell state, formulas, locks, sheets.
- **`AGENTS`** — dict of agent configs loaded from `agents/*.json`. Keyed by agent id (e.g. `"finance"`, `"general"`).
- **`providers`** — dict of `Provider` instances, rebuilt when API keys change. See `_rebuild_providers()`.
- **`PLUGIN_KERNEL`** — `PluginKernel` facade that plugins call to register formulas/agents/models.
- **`app`** — the FastAPI application, created in deps.py and imported by main.py.

Why here: `main.py` is a thin orchestrator (78 lines). It imports `app` from deps, mounts route modules, and serves static files. All initialization (kernel, providers, plugins, middleware) happens at import time in deps.py.

## 6. Running Tests

```bash
python test_platform.py    # Core engine, formulas, macros, collisions
python test_plugins.py     # Plugin loading and registration
python -c "from main import app"   # Smoke test — must import cleanly
```

All tests are offline — no server, no API keys required.
