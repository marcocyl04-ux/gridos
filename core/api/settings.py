"""Settings endpoints: provider keys, model catalog, marketplace."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.api.deps import (
    _mask_key, _persist_api_keys, _rebuild_providers,
    _configured_provider_ids, _providers_for_current_request, _current_user,
    PROVIDER_CLASSES, PROVIDER_DISPLAY_NAMES, PROVIDERS, API_KEYS,
    PLUGINS_DIR, PLUGINS_ENABLED, PLUGIN_KERNEL,
    MODEL_CATALOG, default_model_id, load_plugin_manifests,
    cloud_config, AuthUser, require_user,
    ApiKeySaveRequest, MarketplaceToggleRequest,
)

router = APIRouter()


@router.get("/settings/providers")
async def list_providers(user: AuthUser = Depends(require_user)):
    if cloud_config.SAAS_MODE:
        from cloud import user_keys as _user_keys
        keys = _user_keys.list_keys(user.id) if user and user.id else {}
        providers = []
        for pid in PROVIDER_CLASSES:
            key = keys.get(pid, "")
            providers.append({
                "id": pid,
                "display_name": PROVIDER_DISPLAY_NAMES.get(pid, pid),
                "configured": bool(key),
                "masked_key": _mask_key(key) if key else "",
            })
        return {"providers": providers}
    providers = []
    for pid in PROVIDER_CLASSES:
        key = API_KEYS.get(pid, "")
        providers.append({
            "id": pid,
            "display_name": PROVIDER_DISPLAY_NAMES.get(pid, pid),
            "configured": bool(key and pid in PROVIDERS),
            "masked_key": _mask_key(key) if key else "",
        })
    return {"providers": providers}


@router.post("/settings/keys/save")
async def save_api_key(req: ApiKeySaveRequest, user: AuthUser = Depends(require_user)):
    provider_id = (req.provider or "").strip().lower()
    cls = PROVIDER_CLASSES.get(provider_id)
    if cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")
    api_key = (req.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is empty.")
    try:
        cls(api_key=api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not initialize {provider_id}: {e}")
    if cloud_config.SAAS_MODE:
        from cloud import user_keys as _user_keys
        _user_keys.set_key(user.id, provider_id, api_key)
        return {"status": "Success", "provider": provider_id, "configured": True}
    API_KEYS[provider_id] = api_key
    _persist_api_keys()
    _rebuild_providers()
    return {"status": "Success", "provider": provider_id, "configured": provider_id in PROVIDERS}


@router.delete("/settings/keys/{provider_id}")
async def delete_api_key(provider_id: str, user: AuthUser = Depends(require_user)):
    provider_id = (provider_id or "").strip().lower()
    if provider_id not in PROVIDER_CLASSES:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_id}")
    if cloud_config.SAAS_MODE:
        from cloud import user_keys as _user_keys
        _user_keys.delete_key(user.id, provider_id)
        return {"status": "Success", "provider": provider_id}
    if provider_id in API_KEYS:
        del API_KEYS[provider_id]
        _persist_api_keys()
    _rebuild_providers()
    return {"status": "Success", "provider": provider_id}


@router.get("/marketplace/list")
async def marketplace_list(user: AuthUser = Depends(require_user)):
    manifests = load_plugin_manifests(PLUGINS_DIR)
    loaded_slugs = {r.slug for r in PLUGIN_KERNEL.records}
    loaded_by_slug = {r.slug: r for r in PLUGIN_KERNEL.records}
    load_errors = {e["plugin"]: e["error"] for e in PLUGIN_KERNEL.errors}
    if cloud_config.SAAS_MODE:
        from cloud import marketplace as _marketplace
        installed = _marketplace.list_installed(user.id) if user and user.id else set()
    else:
        installed = set(loaded_slugs)
    out = []
    for m in manifests:
        slug = m["slug"]
        rec = loaded_by_slug.get(slug)
        out.append({
            **m,
            "installed": slug in installed,
            "loaded": slug in loaded_slugs,
            "error": load_errors.get(slug),
            "formulas": list(rec.formulas) if rec else [],
            "agents": list(rec.agents) if rec else [],
            "models": list(rec.models) if rec else [],
        })
    return {"plugins": out, "plugins_enabled": PLUGINS_ENABLED, "mode": "saas" if cloud_config.SAAS_MODE else "oss"}


@router.post("/marketplace/toggle")
async def marketplace_toggle(req: MarketplaceToggleRequest, user: AuthUser = Depends(require_user)):
    manifests = {m["slug"]: m for m in load_plugin_manifests(PLUGINS_DIR)}
    if req.slug not in manifests:
        raise HTTPException(status_code=404, detail=f"Unknown plugin: {req.slug}")
    if not cloud_config.SAAS_MODE:
        return {"status": "Success", "slug": req.slug, "installed": True, "mode": "oss"}
    if not user or not user.id:
        raise HTTPException(status_code=401, detail="Sign in to manage plugins.")
    from cloud import marketplace as _marketplace
    _marketplace.set_installed(user.id, req.slug, req.installed)
    return {"status": "Success", "slug": req.slug, "installed": req.installed}


@router.get("/models/available")
async def list_available_models(user: AuthUser = Depends(require_user)):
    _current_user.set(user)
    configured = _configured_provider_ids(_providers_for_current_request())
    mid = default_model_id(configured)
    models = [
        {**entry, "available": entry["provider"] in configured}
        for entry in MODEL_CATALOG
        if not entry.get("router_only")
    ]
    return {"models": models, "default_model_id": mid, "configured_providers": sorted(configured)}
