"""
Template routes - YAML financial model templates.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

router = APIRouter(prefix="/templates", tags=["templates"])

# ============ Models ============

class TemplateApplyRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    variables: Dict[str, Any] = {}
    target_cell: str = "A1"


class TemplateCreateRequest(BaseModel):
    name: str
    description: str
    yaml_content: str  # Raw YAML


class TemplateListResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str  # "financial", "sales", "custom"
    variables: List[str]


# ============ Routes ============

@router.get("/available")
async def list_templates(workbook_id: Optional[str] = None):
    """
    List all available templates.
    
    Returns:
    [
        {
            "id": "dcf_valuation",
            "name": "DCF Valuation",
            "description": "Discounted Cash Flow model",
            "category": "financial",
            "variables": ["growth_rate", "discount_rate", "terminal_growth"]
        },
        ...
    ]
    """
    raise HTTPException(
        status_code=501,
        detail="List templates not yet migrated to modular structure"
    )


@router.post("/apply/{template_id}")
async def apply_template(
    template_id: str,
    req: TemplateApplyRequest
):
    """
    Apply a template to the current workbook.
    
    Example:
    POST /templates/apply/dcf_valuation
    {
        "variables": {
            "growth_rate": 0.05,
            "discount_rate": 0.10,
            "terminal_growth": 0.03
        },
        "target_cell": "A1"
    }
    
    Returns populated workbook with all cells, formulas, and formatting.
    """
    raise HTTPException(
        status_code=501,
        detail="Apply template not yet migrated to modular structure"
    )


@router.get("/{template_id}")
async def get_template(template_id: str):
    """
    Get template details including the YAML schema.
    """
    raise HTTPException(
        status_code=501,
        detail="Get template not yet migrated to modular structure"
    )


@router.post("/create")
async def create_custom_template(req: TemplateCreateRequest):
    """
    Create a new custom template from YAML.
    
    Templates are stored in assets/templates/ and can be applied like built-ins.
    """
    raise HTTPException(
        status_code=501,
        detail="Create template not yet migrated to modular structure"
    )


@router.post("/{template_id}/clone")
async def clone_template(template_id: str, new_name: str):
    """
    Clone an existing template with a new name.
    """
    raise HTTPException(
        status_code=501,
        detail="Clone template not yet migrated to modular structure"
    )


@router.get("/categories")
async def get_template_categories():
    """
    Get available template categories and descriptions.
    
    Returns:
    {
        "financial": "Financial modeling (DCF, LBO, Comps)",
        "sales": "Sales forecasting and pipeline",
        "operations": "Operations and capacity planning",
        "custom": "User-created templates"
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Categories not yet migrated to modular structure"
    )
