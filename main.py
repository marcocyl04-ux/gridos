"""GridOS — Agentic Workbook.

main.py is a thin orchestrator: it imports shared state from core.api.deps,
mounts route modules, and serves static pages. All endpoint logic lives in
core/api/ route modules. All shared state (kernel pool, providers, macros,
plugin loading) lives in core.api.deps.
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

# Shared state, app object, middleware, and initialization all run on import.
from core.api.deps import app, AGENTS, PLUGINS_ENABLED, PLUGIN_KERNEL

# ---------- Route modules ----------

from core.api.agents import router as agents_router
from core.api.grid import router as grid_router
from core.api.workbooks import router as workbooks_router
from core.api.charts import router as charts_router
from core.api.templates import router as templates_router
from core.api.settings import router as settings_router
from core.api.tools import router as tools_router
from core.api.auth_usage import router as auth_usage_router

app.include_router(agents_router)
app.include_router(grid_router)
app.include_router(workbooks_router)
app.include_router(charts_router)
app.include_router(templates_router)
app.include_router(settings_router)
app.include_router(tools_router)
app.include_router(auth_usage_router)

# ---------- Static pages + health (not worth splitting into modules) ----------

from fastapi.responses import FileResponse


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/plugins")
async def list_plugins():
    return {
        "enabled": PLUGINS_ENABLED,
        "loaded": [r.to_dict() for r in PLUGIN_KERNEL.records],
        "errors": PLUGIN_KERNEL.errors,
    }


@app.get("/")
async def serve_landing():
    return FileResponse("static/landing.html")


@app.get("/workbook")
async def serve_workbook():
    return FileResponse("static/index.html")


@app.get("/login")
async def serve_login():
    return FileResponse("static/login.html")


@app.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"id": a["id"], "display_name": a.get("display_name", a["id"]),
             "router_description": a.get("router_description", "")}
            for a in AGENTS.values()
        ]
    }
