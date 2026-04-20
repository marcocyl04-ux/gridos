"""
GridOS API dependencies — shared state, helpers, kernel pool, provider
registry, macros, model calling, agent routing, prompt building, parsing.

Every route module imports from here. No endpoint definitions live here.
"""

import json
import os
import random
import re
import time
from collections import OrderedDict
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import load_agents
from core.engine import GridOSKernel
from core.functions import FormulaEvaluator
from core.macros import MacroError, compile_macro
from core.models import AgentIntent, WriteResponse
from core.plugins import PluginKernel, discover_and_load as discover_plugins, load_manifests as load_plugin_manifests
from core.providers import (
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    MODEL_CATALOG,
    OpenRouterProvider,
    Provider,
    ProviderAuthError,
    ProviderTransientError,
    default_model_id,
    get_model_entry,
)
from core.utils import a1_to_coords
from core.node_graph import NodeGraph, Coordinator, Executor, Node, NodeType, TypedInterface
from core.intent_parser import IntentParser, validate_with_feedback
from core.declarative_plugins import (
    DeclarativePluginLoader,
    install_declarative_formulas,
    render_yaml_template,
    DEFAULT_MATH_REGISTRY,
)
from core.import_engine import import_file, auto_detect_template
from core.industry_profiles import detect_industry, get_template_instructions


load_dotenv()
TELEMETRY_PATH = Path("telemetry_log.json")
MAX_CHAIN_ITERATIONS = 10

DATA_DIR = Path("data")
TEMPLATES_DIR = DATA_DIR / "templates"
ASSETS_TEMPLATES_DIR = Path("assets") / "templates"  # Deployed YAML templates
MACROS_PATH = DATA_DIR / "user_macros.json"
HERO_TOOLS_PATH = DATA_DIR / "hero_tools.json"
API_KEYS_PATH = DATA_DIR / "api_keys.json"

HERO_TOOLS_CATALOG = [
    {
        "id": "web_search",
        "display_name": "Web Search",
        "description": "(placeholder) Advises the agent that live web lookups are available. Actual fetching is not wired up.",
    },
    {
        "id": "live_data",
        "display_name": "Live Data Puller",
        "description": "(placeholder) Advises the agent that external API/data feeds are available. Actual fetching is not wired up.",
    },
]

app = FastAPI(title="GridOS - Agentic Workbook")

# --- Security middleware: CSRF + Rate Limiting ---
import time as _time
import secrets as _secrets
from collections import defaultdict as _defaultdict

# In-memory rate limiter (per-IP sliding window)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120     # requests per window
_rate_store: dict[str, list[float]] = _defaultdict(list)

CSRF_COOKIE_NAME = "gridos_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def _security_middleware(request, call_next):
    # --- Rate limiting (per IP) ---
    client_ip = request.client.host if request.client else "unknown"
    now = _time.time()
    window = _rate_store[client_ip]
    _rate_store[client_ip] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_store[client_ip]) >= _RATE_LIMIT_MAX:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": "60"},
        )
    _rate_store[client_ip].append(now)

    # --- CSRF protection (double-submit cookie) ---
    if request.method not in _SAFE_METHODS:
        path = request.url.path
        exempt_prefixes = ("/agent/chat", "/agent/apply", "/agent/write", "/agent/execute-graph")
        is_exempt = any(path.startswith(p) for p in exempt_prefixes)
        has_auth = bool(request.headers.get("authorization", "").startswith("Bearer"))
        if not is_exempt and not has_auth:
            csrf_token = request.cookies.get(CSRF_COOKIE_NAME, "")
            csrf_header = request.headers.get(CSRF_HEADER_NAME, "")
            if not csrf_token or csrf_token != csrf_header:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed."},
                )

    response = await call_next(request)
    # Issue CSRF token on safe requests if missing
    if request.method in _SAFE_METHODS and not request.cookies.get(CSRF_COOKIE_NAME):
        token = _secrets.token_urlsafe(32)
        response.set_cookie(
            CSRF_COOKIE_NAME, token,
            httponly=False, samesite="lax", max_age=3600,
        )
    return response


AGENTS = load_agents()

# Plugin loader
PLUGINS_DIR = Path("plugins")
_PLUGINS_ENABLED_ENV = os.environ.get("GRIDOS_PLUGINS_ENABLED")
PLUGINS_ENABLED = (
    _PLUGINS_ENABLED_ENV.strip().lower() in ("1", "true", "yes", "on")
    if _PLUGINS_ENABLED_ENV is not None
    else True
)
if PLUGINS_ENABLED:
    PLUGIN_KERNEL = discover_plugins(PLUGINS_DIR)
    for _plugin_agent_id, _plugin_agent_spec in PLUGIN_KERNEL.agents.items():
        AGENTS[_plugin_agent_id] = _plugin_agent_spec
    MODEL_CATALOG.extend(PLUGIN_KERNEL.models)
    for _rec in PLUGIN_KERNEL.records:
        print(f"[plugins] loaded {_rec.slug}: formulas={_rec.formulas} agents={_rec.agents} models={_rec.models}")
    for _err in PLUGIN_KERNEL.errors:
        print(f"[plugins] ERROR in {_err['plugin']}: {_err['error']}")
else:
    PLUGIN_KERNEL = PluginKernel()

# --- Declarative (YAML) plugin loader ---
DECLARATIVE_LOADER = DeclarativePluginLoader(PLUGINS_DIR)
DECLARATIVE_MANIFESTS = DECLARATIVE_LOADER.load_all()
for _dm in DECLARATIVE_MANIFESTS:
    print(f"[declarative] loaded {_dm.slug}: formulas={len(_dm.formulas)} agents={len(_dm.agents)} templates={len(_dm.templates)}")
for _da_id, _da_spec in DECLARATIVE_LOADER.agent_registry.items():
    if _da_id not in AGENTS:
        AGENTS[_da_id] = {
            "id": _da_spec.id,
            "display_name": _da_spec.display_name,
            "description": _da_spec.description,
            "system_prompt": _da_spec.system_prompt,
            "router_description": _da_spec.router_description,
            "category": _da_spec.category,
        }

# Load YAML templates
_YAML_TEMPLATES: dict[str, dict] = {}
if TEMPLATES_DIR.exists():
    import yaml as _yaml
    for _yt in TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(_yt) as _f:
                _data = _yaml.safe_load(_f)
            if _data and "id" in _data:
                _YAML_TEMPLATES[_data["id"]] = _data
                print(f"[declarative] YAML template: {_data['id']} ({_data.get('name', '')})")
        except Exception as _e:
            print(f"[declarative] Failed to load YAML template {_yt.name}: {_e}")

# Also load from assets/templates/
if ASSETS_TEMPLATES_DIR.exists():
    import yaml as _yaml
    for _yt in ASSETS_TEMPLATES_DIR.glob("*.yaml"):
        try:
            with open(_yt) as _f:
                _data = _yaml.safe_load(_f)
            if _data and "id" in _data:
                if _data["id"] not in _YAML_TEMPLATES:
                    _YAML_TEMPLATES[_data["id"]] = _data
                    print(f"[declarative] YAML template (assets): {_data['id']} ({_data.get('name', '')})")
        except Exception as _e:
            print(f"[declarative] Failed to load YAML template {_yt.name}: {_e}")

# Per-request kernel resolution
_default_kernel = GridOSKernel()
_current_kernel: ContextVar[Optional[GridOSKernel]] = ContextVar("gridos_current_kernel", default=None)
_current_user: ContextVar[Optional["AuthUser"]] = ContextVar("gridos_current_user", default=None)
_kernel_pool: "OrderedDict[tuple[str, str], GridOSKernel]" = OrderedDict()
_kernel_pool_lock = Lock()
KERNEL_POOL_MAX = 64


class _KernelProxy:
    """Reads the per-request kernel from the ContextVar."""
    def __getattr__(self, name: str):
        k = _current_kernel.get()
        if k is None:
            if cloud_config.SAAS_MODE:
                raise RuntimeError(
                    f"kernel.{name} accessed outside a request-scoped kernel in SaaS mode. "
                    "The endpoint is missing `Depends(current_kernel_dep)` on its signature."
                )
            k = _default_kernel
        return getattr(k, name)


kernel = _KernelProxy()

USER_MACROS: list[dict] = []
HERO_TOOLS_STATE: dict[str, bool] = {t["id"]: False for t in HERO_TOOLS_CATALOG}

os.makedirs("static", exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Cloud (SaaS) imports
from cloud import config as cloud_config  # noqa: E402
from cloud import usage as cloud_usage  # noqa: E402
from cloud.auth import AuthUser, optional_user, require_user  # noqa: E402
from cloud.status import router as cloud_status_router  # noqa: E402
from core.workbook_store import FileWorkbookStore, WorkbookScope, WorkbookStore  # noqa: E402
from fastapi import Depends  # noqa: E402

# Install declarative formulas
try:
    install_declarative_formulas(DECLARATIVE_LOADER, _default_kernel)
    print(f"[declarative] Installed {len(DECLARATIVE_LOADER.formula_registry)} formulas into kernel")
except Exception as _e:
    print(f"[declarative] Warning: could not install formulas: {_e}")

app.include_router(cloud_status_router)

# Persistence seam
workbook_store: WorkbookStore
if cloud_config.SAAS_MODE and cloud_config.SAAS_FEATURES["cloud_storage"].enabled:
    from cloud.supabase_store import SupabaseWorkbookStore  # noqa: E402
    workbook_store = SupabaseWorkbookStore(
        url=cloud_config.SUPABASE_URL,
        key=cloud_config.SUPABASE_KEY,
    )
elif cloud_config.SAAS_MODE:
    print("[cloud] SAAS_MODE=true but SUPABASE_URL/KEY missing — /system/save and /system/load will return 503.")
    workbook_store = FileWorkbookStore()
else:
    workbook_store = FileWorkbookStore()


# ---------- Library persistence ----------


def _builtin_primitive_names() -> list[str]:
    return sorted(_default_kernel.evaluator.registry.keys())


def _macro_names() -> set[str]:
    return {m["name"].upper() for m in USER_MACROS}


def _register_macro_into(k: GridOSKernel, spec: dict) -> None:
    macro_name = spec["name"].upper()
    primitive_registry = {
        name: fn for name, fn in k.evaluator.registry.items() if name.upper() != macro_name
    }
    fn = compile_macro(
        name=spec["name"],
        params=spec.get("params", []),
        body=spec["body"],
        registry=primitive_registry,
    )
    k.evaluator.register_custom(macro_name, fn)


def _register_macro(spec: dict) -> None:
    _register_macro_into(_default_kernel, spec)
    with _kernel_pool_lock:
        pool_snapshot = list(_kernel_pool.values())
    for k in pool_snapshot:
        try:
            _register_macro_into(k, spec)
        except MacroError:
            continue


def _unregister_macro(upper_name: str) -> None:
    _default_kernel.evaluator.registry.pop(upper_name, None)
    with _kernel_pool_lock:
        for k in _kernel_pool.values():
            k.evaluator.registry.pop(upper_name, None)


def _load_user_macros() -> None:
    if not MACROS_PATH.exists():
        return
    try:
        raw = json.loads(MACROS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(raw, list):
        return
    for spec in raw:
        try:
            _register_macro(spec)
        except MacroError:
            continue
        USER_MACROS.append({
            "name": spec["name"].upper(),
            "description": spec.get("description", ""),
            "params": [p.upper() for p in spec.get("params", [])],
            "body": spec["body"],
        })


def _persist_user_macros() -> None:
    MACROS_PATH.write_text(json.dumps(USER_MACROS, indent=2), encoding="utf-8")


def _load_hero_tools() -> None:
    if not HERO_TOOLS_PATH.exists():
        return
    try:
        raw = json.loads(HERO_TOOLS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(raw, dict):
        return
    for tool in HERO_TOOLS_CATALOG:
        HERO_TOOLS_STATE[tool["id"]] = bool(raw.get(tool["id"], False))


def _persist_hero_tools() -> None:
    HERO_TOOLS_PATH.write_text(json.dumps(HERO_TOOLS_STATE, indent=2), encoding="utf-8")


_load_user_macros()
_load_hero_tools()


# ---------- Per-request kernel resolution ----------


def _scope_for(user: AuthUser, workbook_id: Optional[str] = None) -> WorkbookScope:
    if not cloud_config.SAAS_MODE:
        return WorkbookScope(user_id=None, workbook_id="default")
    return WorkbookScope(user_id=user.id, workbook_id=workbook_id or user.id)


def _register_macros_into_fresh(k: GridOSKernel) -> None:
    for spec in USER_MACROS:
        try:
            _register_macro_into(k, spec)
        except MacroError:
            continue


def _kernel_for_scope(scope: WorkbookScope) -> GridOSKernel:
    if not cloud_config.SAAS_MODE:
        return _default_kernel

    key = (scope.user_id or "anon", scope.workbook_id or "default")
    with _kernel_pool_lock:
        if key in _kernel_pool:
            _kernel_pool.move_to_end(key)
            return _kernel_pool[key]

    k = GridOSKernel()
    _register_macros_into_fresh(k)
    if scope.user_id:
        try:
            state = workbook_store.load(scope)
            if state:
                k.apply_state_dict(state)
        except Exception as e:
            print(f"[kernel_pool] lazy-load failed for {key}: {e}")

    with _kernel_pool_lock:
        if key in _kernel_pool:
            _kernel_pool.move_to_end(key)
            return _kernel_pool[key]
        _kernel_pool[key] = k
        while len(_kernel_pool) > KERNEL_POOL_MAX:
            _kernel_pool.popitem(last=False)
    return k


async def current_kernel_dep(
    user: AuthUser = Depends(require_user),
    x_workbook_id: Optional[str] = Header(None, alias="X-Workbook-Id"),
    workbook_id: Optional[str] = Query(None),
) -> GridOSKernel:
    wb_id = workbook_id or x_workbook_id
    scope = _scope_for(user, wb_id)
    k = _kernel_for_scope(scope)
    _current_kernel.set(k)
    _current_user.set(user)
    return k


# ---------- Provider registry + API-key storage ----------

PROVIDER_CLASSES: dict[str, type[Provider]] = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
}
PROVIDER_DISPLAY_NAMES = {
    "gemini": "Google Gemini",
    "anthropic": "Anthropic Claude",
    "groq": "Groq",
    "openrouter": "OpenRouter",
}
PROVIDERS: dict[str, Provider] = {}
API_KEYS: dict[str, str] = {}


def _load_api_keys_from_disk() -> dict[str, str]:
    if not API_KEYS_PATH.exists():
        return {}
    try:
        raw = json.loads(API_KEYS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}


def _persist_api_keys() -> None:
    API_KEYS_PATH.write_text(json.dumps(API_KEYS, indent=2), encoding="utf-8")


def _seed_keys_from_env(keys: dict[str, str]) -> dict[str, str]:
    env_map = {
        "gemini": os.environ.get("GOOGLE_API_KEY"),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "groq": os.environ.get("GROQ_API_KEY"),
        "openrouter": os.environ.get("OPENROUTER_API_KEY"),
    }
    for pid, env_val in env_map.items():
        if pid not in keys and env_val:
            keys[pid] = env_val
    return keys


def _rebuild_providers() -> None:
    PROVIDERS.clear()
    for provider_id, key in API_KEYS.items():
        cls = PROVIDER_CLASSES.get(provider_id)
        if not cls or not key:
            continue
        try:
            PROVIDERS[provider_id] = cls(api_key=key)
        except Exception as e:
            print(f"[providers] Failed to init {provider_id}: {e}")


API_KEYS.update(_seed_keys_from_env(_load_api_keys_from_disk()))
_rebuild_providers()


def _configured_provider_ids(providers: Optional[Dict[str, Provider]] = None) -> set[str]:
    return set((providers if providers is not None else PROVIDERS).keys())


def _providers_for_current_request() -> Dict[str, Provider]:
    if not cloud_config.SAAS_MODE:
        return PROVIDERS
    user = _current_user.get()
    if not user or not getattr(user, "id", None):
        return {}
    from cloud import user_keys as _user_keys  # lazy import
    keys = _user_keys.list_keys(user.id)
    providers: Dict[str, Provider] = {}
    for pid, key in keys.items():
        cls = PROVIDER_CLASSES.get(pid)
        if not cls or not key:
            continue
        try:
            providers[pid] = cls(api_key=key)
        except Exception as e:
            print(f"[user_keys] {pid} init failed for user {user.id}: {e}")
    return providers


def _resolve_model(
    model_id: Optional[str],
    providers: Optional[Dict[str, Provider]] = None,
    *,
    allow_router_only: bool = False,
) -> tuple[str, Provider]:
    if providers is None:
        providers = _providers_for_current_request()
    configured = _configured_provider_ids(providers)
    if not configured:
        raise HTTPException(
            status_code=400,
            detail="No LLM provider is configured. Add an API key in Settings.",
        )
    entry = get_model_entry(model_id) if model_id else None
    if entry and entry["provider"] in providers:
        if entry.get("router_only") and not allow_router_only:
            entry = None
        else:
            return entry["id"], providers[entry["provider"]]
    fallback_id = default_model_id(configured)
    if not fallback_id:
        raise HTTPException(status_code=400, detail="No usable model available.")
    fallback_entry = get_model_entry(fallback_id)
    return fallback_entry["id"], providers[fallback_entry["provider"]]


# ---------- Telemetry ----------


def _append_telemetry(entry: dict) -> None:
    existing: list = []
    if TELEMETRY_PATH.exists():
        try:
            existing = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    TELEMETRY_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def call_model(
    agent_id: str,
    *,
    system_instruction: str,
    user_message: str,
    model_id: Optional[str] = None,
    max_attempts: int = 4,
    max_output_tokens: Optional[int] = None,
):
    model, provider = _resolve_model(model_id, allow_router_only=(agent_id == "router"))

    last_exc: Optional[Exception] = None
    response = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = provider.generate(
                model=model,
                system_instruction=system_instruction,
                user_message=user_message,
                max_output_tokens=max_output_tokens,
            )
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not provider.is_transient_error(exc):
                raise
            delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            time.sleep(delay)
    if response is None:
        if last_exc:
            raise last_exc
        raise RuntimeError("call_model exhausted retries with no response")

    _append_telemetry({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "provider": provider.id,
        "model": response.model,
        "prompt_token_count": response.prompt_tokens,
        "candidates_token_count": response.candidates_tokens,
        "total_token_count": response.total_tokens,
        "finish_reason": response.finish_reason,
    })
    cloud_usage.log_call(
        provider=provider.id,
        model=response.model,
        prompt_tokens=response.prompt_tokens or 0,
        completion_tokens=response.candidates_tokens or 0,
        finish_reason=response.finish_reason,
    )
    return response


def _classify_model_error(exc: Exception) -> str:
    for provider in PROVIDERS.values():
        if provider.is_auth_error(exc):
            return "auth"
        if provider.is_transient_error(exc):
            return "transient"
    return "other"


# ---------- Request models ----------


class ChatRequest(BaseModel):
    prompt: str
    history: List[Dict[str, str]] = []
    scope: str = "sheet"
    selected_cells: List[str] = []
    sheet: Optional[str] = None
    model_id: Optional[str] = None


class ChainRequest(ChatRequest):
    max_iterations: int = MAX_CHAIN_ITERATIONS


class ApiKeySaveRequest(BaseModel):
    provider: str
    api_key: str


class FormulaRequest(BaseModel):
    function_name: str
    arguments: list[float]


class CellUpdateRequest(BaseModel):
    cell: str
    value: Optional[str] = ""
    sheet: Optional[str] = None


class RangeUpdateRequest(BaseModel):
    target_cell: str
    values: list[list[str | int | float | bool | None]]
    sheet: Optional[str] = None


class PreviewApplyRequest(BaseModel):
    sheet: Optional[str] = None
    agent_id: str
    target_cell: Optional[str] = None
    values: Optional[list[list]] = None
    intents: Optional[list[Dict[str, Any]]] = None
    shift_direction: str = "right"
    chart_spec: Optional[Dict[str, Any]] = None


class SheetCreateRequest(BaseModel):
    name: Optional[str] = None


class SheetRenameRequest(BaseModel):
    old_name: str
    new_name: str


class SheetActivateRequest(BaseModel):
    name: str


class WorkbookRenameRequest(BaseModel):
    name: str


class WorkbookCreateRequest(BaseModel):
    title: Optional[str] = None


class WorkbookRenameSaasRequest(BaseModel):
    title: str


class ChatLogReplaceRequest(BaseModel):
    entries: List[Dict[str, Any]] = []


class CellClearRequest(BaseModel):
    cells: List[str]
    sheet: Optional[str] = None


class CellFormatRequest(BaseModel):
    cells: List[str]
    decimals: Optional[int] = None
    sheet: Optional[str] = None


class NodeGraphRequest(BaseModel):
    """Execute via typed node graph (advanced agent workflows)."""
    llm_response: Dict[str, Any]
    prompt: str = ""
    agent_id: str = "general"


class ChartCreateRequest(BaseModel):
    anchor_cell: str = "F2"
    data_range: str
    chart_type: str = "bar"
    title: str = ""
    width: int = 400
    height: int = 280
    orientation: str = "columns"
    sheet: Optional[str] = None


class ChartUpdateRequest(BaseModel):
    anchor_cell: Optional[str] = None
    data_range: Optional[str] = None
    chart_type: Optional[str] = None
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[str] = None
    sheet: Optional[str] = None


class TemplateSaveRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class MacroSaveRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    params: List[str] = []
    body: str


class HeroToolToggleRequest(BaseModel):
    tool_id: str
    enabled: bool


class MarketplaceToggleRequest(BaseModel):
    slug: str
    installed: bool


# ---------- Agent routing & prompts ----------


BASE_SYSTEM_RULES = (
    "You are operating within GridOS. Check the \"locked\" metadata for every cell "
    "before proposing a write. Do not attempt to overwrite locked cells."
)

OUTPUT_FORMAT_SPEC = """
OUTPUT FORMAT: strictly valid JSON (no markdown fences). Two write shapes — pick whichever fits the task in ONE LLM call.

(a) SINGLE-rectangle write — for one label, one row, one column, one N×M block:
{
    "reasoning": "Short explanation.",
    "target_cell": "A1",
    "values": [["..."]],
    "chart_spec": null,
    "macro_spec": null,
    "plan": null
}

(b) MULTI-rectangle write — for any structured artifact with multiple named sections (3-statement model, full operating model / pro-forma / DCF / budget, multi-block dashboard, anything where the user asks for a deliverable that's clearly more than one rectangle). Pack EVERY section into ONE response so the kernel applies them atomically with one Apply click and the user pays for ONE LLM call instead of N chain turns:
{
    "reasoning": "Built complete 3-statement model anchored at B2.",
    "intents": [
        {"target_cell": "B2",  "values": [["Income Statement", "Q1", "Q2", "Q3", "Q4"]]},
        {"target_cell": "B3",  "values": [["Revenue", 100, "=MULTIPLY(C3,1.1)", "=MULTIPLY(D3,1.1)", "=MULTIPLY(E3,1.1)"]]},
        {"target_cell": "B4",  "values": [["COGS", "=MULTIPLY(C3,0.4)", "=MULTIPLY(D3,0.4)", "=MULTIPLY(E3,0.4)", "=MULTIPLY(F3,0.4)"]]},
        {"target_cell": "B5",  "values": [["Gross profit", "=MINUS(C3,C4)", "=MINUS(D3,D4)", "=MINUS(E3,E4)", "=MINUS(F3,F4)"]]},
        {"target_cell": "B13", "values": [["Balance Sheet", "Q1", "Q2", "Q3", "Q4"]]},
        ...
    ],
    "chart_spec": null,
    "macro_spec": null,
    "plan": { "title": "...", "anchor": "B2", "sections": [...] }
}
When using `intents`, leave top-level `target_cell` and `values` null. Intents apply in order, so later intents may reference cells written by earlier ones. The agent system prompt's "one contiguous rectangle per response" rule constrains the SHAPE of each rectangle (each `values` must still be a contiguous rectangle, no holes), NOT the number of rectangles you may emit.

WHICH SHAPE TO USE:
- The user asks for a single value, label, or one row/column/block → (a) SINGLE.
- The user asks for a structured deliverable with 3+ named sections → (b) MULTI. Always prefer (b) over chain mode for these — same result, ~6× cheaper in tokens and faster wall-clock.

Always include a `plan` alongside `intents` when building a model — it tells the user what they're about to apply and gives them a mental map.

If the user asks for a chart/graph/visualization, also fill in chart_spec:
{
    "data_range": "A1:B6",        // rectangular range covering labels + values
    "chart_type": "bar",          // one of: bar, line, pie
    "title": "Scores",
    "anchor_cell": "D2",          // top-left cell where the chart overlay appears; pick an empty area
    "orientation": "columns"      // "columns" = first column is labels (typical); "rows" = first row is labels
}
Omit chart_spec (leave as null) when the user is only writing data or editing cells.

If the user asks for a NEW named formula/metric that is not already listed in USER MACROS or the built-in primitives, you MAY propose a new macro by filling in macro_spec:
{
    "name": "MARGIN",                    // unique identifier, letters/digits/underscore only
    "params": ["A", "B"],                // parameter names (uppercase letters)
    "description": "Gross margin: (A - B) / A",
    "body": "=DIVIDE(MINUS(A, B), A)"   // MUST only call registered primitives. Nested primitive calls ARE allowed here (this is the one place nesting is permitted — macro bodies are composed expressions). No infix operators, no references to other user macros.
}
Proposed macros are NOT saved automatically — the user reviews and approves them. In the SAME response, do NOT write any cell values that call the proposed macro (it isn't registered yet). Keep "values" null or write unrelated cells. The user will re-ask after approval to use the new macro.
""".strip()


_ROUTER_MODEL_PREFERENCE = [
    ("llama-3.1-8b-instant", "groq"),
    ("gemini-3.1-flash-lite-preview", "gemini"),
    ("claude-haiku-4-5-20251001", "anthropic"),
    ("meta-llama/llama-3.2-3b-instruct:free", "openrouter"),
]


def _pick_router_model(user_choice: Optional[str]) -> Optional[str]:
    configured = _configured_provider_ids(_providers_for_current_request())
    for mid, pid in _ROUTER_MODEL_PREFERENCE:
        if pid in configured:
            return mid
    return user_choice


_ROUTER_PROMPT_CHAR_CAP = 800
_ROUTER_HISTORY_CHAR_CAP = 400


def route_prompt(prompt: str, history_context: str, model_id: Optional[str] = None) -> str:
    if len(AGENTS) == 1:
        return next(iter(AGENTS))

    safe_prompt = (prompt or "")[:_ROUTER_PROMPT_CHAR_CAP]
    safe_history = (history_context or "")[:_ROUTER_HISTORY_CHAR_CAP]

    options = "\n".join(
        f"- {agent['id']}: {agent.get('router_description', agent.get('display_name', agent['id']))}"
        for agent in AGENTS.values()
    )
    instruction = f"""
Analyze this user task: "{safe_prompt}".
Previous context: {safe_history}

Available agent profiles:
{options}

Return ONLY the lowercase agent id that best fits the task. No other text.
""".strip()

    res = call_model(
        "router",
        system_instruction="You are a routing classifier. Respond with only a lowercase agent id.",
        user_message=instruction,
        model_id=_pick_router_model(model_id),
        max_output_tokens=32,
    )
    candidate = res.text.strip().lower().split()[0] if res.text else "general"
    return candidate if candidate in AGENTS else "general"


def build_system_instruction(agent: dict, context: dict, req: ChatRequest) -> str:
    selected_summary = ", ".join(req.selected_cells) if req.selected_cells else "No cells selected."
    scope_line = "Selected cells only" if req.scope == "selection" else "Entire active sheet"
    bounds = context.get("occupied_bounds")
    bounds_line = (
        f"Occupied region: {bounds['top_left']} -> {bounds['bottom_right']} "
        f"({bounds['rows']} rows x {bounds['cols']} cols)"
        if bounds else "Occupied region: empty"
    )

    existing_charts = kernel.list_charts(req.sheet or kernel.active_sheet)
    if existing_charts:
        chart_lines = [
            f"- \"{c.get('title') or '(untitled)'}\" ({c.get('chart_type')}, range {c.get('data_range')}, anchor {c.get('anchor_cell')})"
            for c in existing_charts
        ]
        charts_section = "EXISTING CHARTS ON THIS SHEET (reuse the same title in chart_spec to update one):\n" + "\n".join(chart_lines)
    else:
        charts_section = "EXISTING CHARTS ON THIS SHEET: none"

    if USER_MACROS:
        macro_lines = [
            f"- {m['name']}({', '.join(m['params'])}) — {m.get('description') or 'user macro'}"
            for m in USER_MACROS
        ]
        macros_section = (
            "USER MACROS (callable like built-in formulas, single flat call, no nesting in the grid):\n"
            + "\n".join(macro_lines)
        )
    else:
        macros_section = "USER MACROS: none"

    enabled_hero_ids = [t["id"] for t in HERO_TOOLS_CATALOG if HERO_TOOLS_STATE.get(t["id"])]
    if enabled_hero_ids:
        hero_lines = [
            f"- {t['display_name']}: {t['description']}"
            for t in HERO_TOOLS_CATALOG
            if t["id"] in enabled_hero_ids
        ]
        hero_section = (
            "HERO TOOLS ENABLED (advisory — they are not wired up yet, mention capability only if the user asks):\n"
            + "\n".join(hero_lines)
        )
    else:
        hero_section = "HERO TOOLS ENABLED: none"

    primitive_names = _builtin_primitive_names()
    primitives_section = (
        "AVAILABLE PRIMITIVES (authoritative — if a function is not in this list, it does NOT exist; "
        "do not invent names like POWER, LN, IF, etc. unless they appear here):\n"
        + ", ".join(primitive_names)
    )

    sections = [
        BASE_SYSTEM_RULES,
        f"ACTIVE SHEET: {req.sheet or kernel.active_sheet}\nVIEW SCOPE: {scope_line}\nSELECTED CELLS: {selected_summary}\n{bounds_line}",
        f"CELL METADATA (a1 -> {{val, locked, type}}):\n{context['cell_metadata_json']}",
        f"READABLE GRID STATE:\n{context['formatted_data']}",
        charts_section,
        primitives_section,
        macros_section,
        hero_section,
    ]

    trimmed = _trim_history(req.history)
    if trimmed:
        history_lines = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in trimmed)
        sections.append(
            "CONVERSATION HISTORY (most recent ~6 turns, each truncated to ~600 chars; the first "
            "user message is the original task — check it for any targets you have not yet written):\n"
            + history_lines
        )

    sections.extend([agent["system_prompt"], OUTPUT_FORMAT_SPEC])
    return "\n\n".join(sections)


def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_ai_response(response) -> dict:
    text = (response.text or "").replace("```json", "").replace("```", "").strip()

    finish = response.finish_reason
    ctx = f"{response.provider_id}/{response.model}"
    if finish:
        ctx += f" (finish_reason={finish})"

    if not text:
        hint = (
            "hit the output-token cap — try a shorter prompt or a model with more headroom"
            if finish and ("length" in str(finish).lower() or str(finish).upper() == "MAX_TOKENS")
            else "returned no content — try a stronger model (Gemini/Claude) or rephrase"
        )
        raise HTTPException(
            status_code=422,
            detail=f"Model {ctx} {hint}.",
        )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    extracted = _extract_first_json_object(text)
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    preview = text[:180].replace("\n", " ")
    raise HTTPException(
        status_code=422,
        detail=(
            f"Model {ctx} returned non-JSON output — try a stronger model (Gemini/Claude) "
            f"or rephrase. First bytes: {preview!r}"
        ),
    )


def _sanitize_plan(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    sections_raw = raw.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None
    sections = []
    for item in sections_raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        target = str(item.get("target") or "").strip()
        notes = str(item.get("notes") or "").strip()
        if not label and not target and not notes:
            continue
        sections.append({"label": label, "target": target, "notes": notes})
    if not sections:
        return None
    return {
        "title": str(raw.get("title") or "").strip(),
        "anchor": str(raw.get("anchor") or "").strip(),
        "sections": sections,
    }


def _normalize_multi_intents(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        target = item.get("target_cell")
        values = item.get("values")
        if not isinstance(target, str) or not target.strip():
            continue
        if not isinstance(values, list) or not values:
            continue
        any_real = any(
            any(v not in ("", None) for v in row)
            for row in values if isinstance(row, list)
        )
        if not any_real:
            continue
        out.append({"target_cell": target.upper().strip(), "values": values})
    return out


def _validate_proposed_macro(raw: Any) -> tuple[Optional[dict], Optional[str]]:
    if not raw or not isinstance(raw, dict):
        return None, None
    name = str(raw.get("name") or "").strip()
    body = str(raw.get("body") or "").strip()
    if not name or not body:
        return None, "Macro proposal missing name or body."
    params_raw = raw.get("params") or []
    if not isinstance(params_raw, list):
        return None, "Macro params must be a list."
    params = [str(p).strip() for p in params_raw if str(p).strip()]

    upper = name.upper()
    existing_macro_names = _macro_names()
    if upper in existing_macro_names:
        registry = {k: v for k, v in kernel.evaluator.registry.items() if k.upper() != upper}
    else:
        registry = dict(kernel.evaluator.registry)
    try:
        compile_macro(name=name, params=params, body=body, registry=registry)
    except MacroError as e:
        return None, str(e)

    return {
        "name": upper,
        "params": [p.upper() for p in params],
        "description": str(raw.get("description") or "").strip(),
        "body": body,
        "replaces_existing": upper in _macro_names(),
    }, None


def _trim_history(history: list, max_turns: int = 6, max_chars: int = 600) -> list:
    if not history:
        return []
    tail = history[-max_turns:]
    out = []
    for h in tail:
        content = str(h.get("content", ""))
        if len(content) > max_chars:
            content = content[:max_chars] + " …[truncated]"
        out.append({"role": h.get("role", "user"), "content": content})
    return out


_CELL_REF_RE = re.compile(r"[A-Z]+\d+")


def _find_empty_formula_deps(preview_cells: list[dict], sheet_state: dict) -> list[dict]:
    self_written_nonempty: set[str] = set()
    for p in preview_cells:
        v = p.get("value")
        if v not in (None, ""):
            self_written_nonempty.add(p["cell"].upper())

    issues: list[dict] = []
    for p in preview_cells:
        v = p.get("value")
        if not isinstance(v, str) or not v.startswith("="):
            continue
        empty_refs: list[str] = []
        for ref in _CELL_REF_RE.findall(v.upper()):
            if ref in self_written_nonempty:
                continue
            try:
                r, c = a1_to_coords(ref)
            except ValueError:
                continue
            cell = sheet_state["cells"].get((r, c))
            if cell is None:
                empty_refs.append(ref)
            elif cell.value in (None, "") and not cell.formula:
                empty_refs.append(ref)
        if empty_refs:
            issues.append({
                "cell": p["cell"],
                "formula": v,
                "empty_refs": empty_refs,
            })
    return issues


def _formula_references_text_cell(formula: str, sheet_state: dict) -> list[str]:
    bad_refs: list[str] = []
    for ref in _CELL_REF_RE.findall(formula.upper()):
        try:
            r, c = a1_to_coords(ref)
        except ValueError:
            continue
        cell = sheet_state["cells"].get((r, c))
        if cell is None:
            continue
        v = cell.value
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            continue
        if v in ("", None):
            continue
        bad_refs.append(ref)
    return bad_refs


def _observe_written_cells(preview_cells: list[dict], sheet: str) -> list[dict]:
    state = kernel._sheet_state(sheet)
    observations = []
    for item in preview_cells:
        a1 = item["cell"]
        try:
            r, c = a1_to_coords(a1)
        except ValueError:
            continue
        cell = state["cells"].get((r, c))
        if cell is None:
            continue
        warning = None
        if cell.formula:
            bad_refs = _formula_references_text_cell(cell.formula, state)
            if bad_refs:
                labels = ", ".join(f"{ref}={state['cells'][a1_to_coords(ref)].value!r}" for ref in bad_refs)
                warning = (
                    f"Formula in {a1} references non-numeric cell(s): {labels}. "
                    f"This is the COLUMN ALIGNMENT bug — the formula in column "
                    f"{a1.rstrip('0123456789')} must reference cells in column "
                    f"{a1.rstrip('0123456789')}, not a label column."
                )
        observations.append({
            "cell": a1,
            "value": cell.value,
            "formula": cell.formula,
            "warning": warning,
        })
    return observations


def _is_completion_signal(values) -> bool:
    if not values:
        return True
    for row in values:
        for v in row:
            if v not in ("", None):
                return False
    return True


def generate_agent_preview(req: ChatRequest) -> dict:
    sheet = req.sheet or kernel.active_sheet
    context = kernel.get_context_for_ai(sheet, req.selected_cells, req.scope)
    agent_id = route_prompt(req.prompt, "", model_id=req.model_id)
    agent = AGENTS[agent_id]
    system_instruction = build_system_instruction(agent, context, req)

    final_response = call_model(
        agent_id,
        system_instruction=system_instruction,
        user_message=req.prompt,
        model_id=req.model_id,
    )
    ai_data = _parse_ai_response(final_response)

    raw_values = ai_data.get("values")
    raw_target = ai_data.get("target_cell")
    raw_intents = ai_data.get("intents")
    chart_spec = ai_data.get("chart_spec")
    proposed_macro, macro_error = _validate_proposed_macro(ai_data.get("macro_spec"))
    plan = _sanitize_plan(ai_data.get("plan"))
    fallback_target = req.selected_cells[0] if req.selected_cells else "A1"

    multi_intents = _normalize_multi_intents(raw_intents)
    if multi_intents:
        merged_preview_cells: list[dict] = []
        echoed_intents: list[dict] = []
        for vi in multi_intents:
            sub_intent = AgentIntent(
                agent_id=agent_id,
                target_start_a1=vi["target_cell"],
                data_payload=vi["values"],
                shift_direction="right",
            )
            sub_preview = kernel.preview_agent_intent(sub_intent, sheet)
            merged_preview_cells.extend(sub_preview["preview_cells"])
            echoed_intents.append({
                "target_cell": sub_preview["actual_target"],
                "original_request": sub_preview["original_target"],
                "values": vi["values"],
            })

        dep_issues = _find_empty_formula_deps(merged_preview_cells, kernel._sheet_state(sheet))
        if dep_issues:
            bullets = "\n".join(
                f"  - {d['cell']} ({d['formula']}) references empty cell(s): {', '.join(d['empty_refs'])}"
                for d in dep_issues[:5]
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    "The agent proposed formulas whose inputs are empty — applying would produce "
                    "#DIV/0! or misleading zeros. Re-ask the agent to also populate the referenced "
                    "cells, or fill them yourself first.\n" + bullets
                ),
            )

        return {
            "category": agent_id,
            "reasoning": ai_data.get("reasoning"),
            "sheet": sheet,
            "scope": req.scope,
            "selected_cells": req.selected_cells,
            "agent_id": agent_id,
            "target_cell": echoed_intents[0]["target_cell"],
            "original_request": echoed_intents[0]["original_request"],
            "preview_cells": merged_preview_cells,
            "values": None,
            "intents": echoed_intents,
            "chart_spec": chart_spec,
            "proposed_macro": proposed_macro,
            "macro_error": macro_error,
            "plan": plan,
        }

    has_values = isinstance(raw_values, list) and any(
        any(v not in ("", None) for v in row) for row in raw_values if isinstance(row, list)
    )

    if not has_values:
        return {
            "category": agent_id,
            "reasoning": ai_data.get("reasoning"),
            "sheet": sheet,
            "scope": req.scope,
            "selected_cells": req.selected_cells,
            "agent_id": agent_id,
            "target_cell": raw_target or fallback_target,
            "original_request": raw_target or fallback_target,
            "preview_cells": [],
            "values": None,
            "chart_spec": chart_spec,
            "proposed_macro": proposed_macro,
            "macro_error": macro_error,
            "plan": plan,
        }

    intent = AgentIntent(
        agent_id=agent_id,
        target_start_a1=raw_target or fallback_target,
        data_payload=raw_values,
        shift_direction="right",
    )

    preview = kernel.preview_agent_intent(intent, sheet)

    dep_issues = _find_empty_formula_deps(
        preview["preview_cells"],
        kernel._sheet_state(sheet),
    )
    if dep_issues:
        bullets = "\n".join(
            f"  - {d['cell']} ({d['formula']}) references empty cell(s): {', '.join(d['empty_refs'])}"
            for d in dep_issues[:5]
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "The agent proposed formulas whose inputs are empty — applying would produce "
                "#DIV/0! or misleading zeros. Re-ask the agent to also populate the referenced "
                "cells, or fill them yourself first.\n" + bullets
            ),
        )

    return {
        "category": agent_id,
        "reasoning": ai_data.get("reasoning"),
        "sheet": sheet,
        "scope": req.scope,
        "selected_cells": req.selected_cells,
        "agent_id": agent_id,
        "target_cell": preview["actual_target"],
        "original_request": preview["original_target"],
        "preview_cells": preview["preview_cells"],
        "values": raw_values,
        "chart_spec": chart_spec,
        "proposed_macro": proposed_macro,
        "macro_error": macro_error,
        "plan": plan,
    }


# ---------- Template helpers ----------

_TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _slugify_template_name(name: str) -> str:
    slug = _SAFE_SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "template"


def _template_path(template_id: str) -> Path:
    if not _TEMPLATE_ID_RE.match(template_id):
        raise HTTPException(status_code=400, detail="Invalid template id.")
    return TEMPLATES_DIR / f"{template_id}.json"


def _template_summary(payload: dict) -> dict:
    state = payload.get("state") or {}
    sheets = state.get("sheets") or {}
    cell_count = 0
    for sheet in sheets.values():
        cell_count += len((sheet or {}).get("cells") or {})
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "description": payload.get("description", ""),
        "author": payload.get("author") or "You",
        "created_at": payload.get("created_at"),
        "sheet_count": len(sheets),
        "cell_count": cell_count,
    }


# ---------- Settings helpers ----------


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


# ---------- SaaS guard ----------


def _require_saas_storage() -> None:
    if not cloud_config.SAAS_MODE:
        raise HTTPException(status_code=404, detail="Multi-workbook is a SaaS feature.")
    if not cloud_config.SAAS_FEATURES["cloud_storage"].enabled:
        raise HTTPException(status_code=503, detail="Cloud storage is not configured.")
