"""Templates endpoints: save, list, load, apply, delete (JSON + YAML)."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.api.deps import (
    kernel, current_kernel_dep, GridOSKernel,
    _slugify_template_name, _template_path, _template_summary,
    TEMPLATES_DIR, _YAML_TEMPLATES, _TEMPLATE_ID_RE,
)

router = APIRouter()


class TemplateSaveRequest(BaseModel):
    name: str
    description: Optional[str] = ""


@router.post("/templates/save")
async def save_template(req: TemplateSaveRequest, k: GridOSKernel = Depends(current_kernel_dep)):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Template name is required.")
    base_slug = _slugify_template_name(req.name)
    candidate = base_slug
    counter = 2
    while (TEMPLATES_DIR / f"{candidate}.json").exists():
        candidate = f"{base_slug}-{counter}"
        counter += 1
    created_at = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "id": candidate,
        "name": req.name.strip(),
        "description": (req.description or "").strip(),
        "author": "You",
        "created_at": created_at,
        "state": kernel.export_state_dict(),
    }
    (TEMPLATES_DIR / f"{candidate}.json").write_text(
        json.dumps(snapshot, indent=2), encoding="utf-8"
    )
    return {"status": "Success", "template": _template_summary(snapshot)}


@router.get("/templates/list")
async def list_templates():
    templates: list[dict] = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        templates.append(_template_summary(payload))
    templates.sort(key=lambda t: t.get("created_at") or "", reverse=True)
    yaml_templates = [
        {
            "id": tid,
            "name": t.get("name", tid),
            "description": t.get("description", ""),
            "category": t.get("category", ""),
        }
        for tid, t in _YAML_TEMPLATES.items()
    ]
    return {"templates": templates, "yaml_templates": yaml_templates}


@router.get("/templates/load/{template_id}")
async def load_template(template_id: str):
    path = _template_path(template_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/templates/apply/{template_id}")
async def apply_template(template_id: str, k: GridOSKernel = Depends(current_kernel_dep)):
    if template_id in _YAML_TEMPLATES:
        yaml_template = _YAML_TEMPLATES[template_id]
        try:
            from core.declarative_plugins import render_yaml_template
            state = render_yaml_template(yaml_template)
            result = kernel.apply_template_respecting_locks(state)
            return {"status": "Success", **result, "source": "yaml"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not apply YAML template: {e}")
    path = _template_path(template_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        result = kernel.apply_template_respecting_locks(payload.get("state") or {})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not apply template: {e}")
    return {"status": "Success", **result, "source": "json"}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    path = _template_path(template_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    path.unlink()
    return {"status": "Success"}
