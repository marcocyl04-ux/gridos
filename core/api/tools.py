"""Tools endpoints: macros, hero tools, formula evaluate, primitives."""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.macros import MacroError
from core.functions import FormulaEvaluator
from core.api.deps import (
    kernel, current_kernel_dep, GridOSKernel,
    _builtin_primitive_names, _macro_names,
    _register_macro, _unregister_macro, _persist_user_macros, _persist_hero_tools,
    USER_MACROS, HERO_TOOLS_STATE, HERO_TOOLS_CATALOG, PLUGIN_KERNEL,
    cloud_config, AuthUser, require_user,
    MacroSaveRequest, HeroToolToggleRequest, FormulaRequest,
)

router = APIRouter()


@router.get("/tools/list")
async def list_tools(user: AuthUser = Depends(require_user)):
    plugin_formula_to_slug: dict[str, str] = {}
    for rec in PLUGIN_KERNEL.records:
        for fname in rec.formulas:
            plugin_formula_to_slug[fname.upper()] = rec.slug
    if cloud_config.SAAS_MODE and user and user.id:
        from cloud import marketplace as _marketplace
        installed_slugs = _marketplace.list_installed(user.id)
    else:
        installed_slugs = {r.slug for r in PLUGIN_KERNEL.records}
    primitives = []
    for name in _builtin_primitive_names():
        upper = name.upper()
        if upper in _macro_names():
            continue
        owning_slug = plugin_formula_to_slug.get(upper)
        if owning_slug is not None and owning_slug not in installed_slugs:
            continue
        primitives.append({"name": name, "builtin": True})
    return {
        "primitives": primitives,
        "macros": [dict(m) for m in USER_MACROS],
        "hero_tools": [
            {"id": t["id"], "display_name": t["display_name"], "description": t["description"],
             "enabled": bool(HERO_TOOLS_STATE.get(t["id"], False))}
            for t in HERO_TOOLS_CATALOG
        ],
    }


@router.post("/tools/save_macro")
async def save_macro(req: MacroSaveRequest):
    clean_name = (req.name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Macro name is required.")
    clean_body = (req.body or "").strip()
    if not clean_body:
        raise HTTPException(status_code=400, detail="Macro body is required.")
    spec = {"name": clean_name, "description": (req.description or "").strip(),
            "params": list(req.params or []), "body": clean_body}
    try:
        _register_macro(spec)
    except MacroError as e:
        raise HTTPException(status_code=400, detail=str(e))
    normalized = {"name": clean_name.upper(), "description": spec["description"],
                  "params": [p.upper() for p in spec["params"]], "body": clean_body}
    replaced = False
    for idx, existing in enumerate(USER_MACROS):
        if existing["name"] == normalized["name"]:
            USER_MACROS[idx] = normalized
            replaced = True
            break
    if not replaced:
        USER_MACROS.append(normalized)
    _persist_user_macros()
    return {"status": "Success", "macro": normalized, "replaced": replaced}


@router.delete("/tools/macros/{macro_name}")
async def delete_macro(macro_name: str):
    upper = macro_name.upper()
    removed = False
    for idx, existing in enumerate(list(USER_MACROS)):
        if existing["name"] == upper:
            USER_MACROS.pop(idx)
            removed = True
            break
    if not removed:
        raise HTTPException(status_code=404, detail=f"Macro '{macro_name}' not found.")
    _unregister_macro(upper)
    _persist_user_macros()
    return {"status": "Success"}


@router.post("/tools/hero/toggle")
async def toggle_hero_tool(req: HeroToolToggleRequest):
    if req.tool_id not in HERO_TOOLS_STATE:
        raise HTTPException(status_code=404, detail=f"Unknown hero tool '{req.tool_id}'.")
    HERO_TOOLS_STATE[req.tool_id] = bool(req.enabled)
    _persist_hero_tools()
    return {"status": "Success", "tool_id": req.tool_id, "enabled": HERO_TOOLS_STATE[req.tool_id]}


@router.post("/formula/evaluate")
async def evaluate_formula(req: FormulaRequest):
    evaluator = FormulaEvaluator()
    return {"result": evaluator.evaluate(req.function_name, req.arguments)}
