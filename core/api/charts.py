"""Charts endpoints: CRUD for chart overlays."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from core.api.deps import kernel, current_kernel_dep, GridOSKernel, ChartCreateRequest, ChartUpdateRequest

router = APIRouter()

@router.get("/system/charts")
async def list_charts(sheet: Optional[str] = None, k: GridOSKernel = Depends(current_kernel_dep)):
    return {"charts": kernel.list_charts(sheet)}

@router.post("/system/charts")
async def create_chart(req: ChartCreateRequest, k: GridOSKernel = Depends(current_kernel_dep)):
    spec = req.model_dump(exclude={"sheet"})
    try:
        chart = kernel.add_chart(spec, sheet_name=req.sheet)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create chart: {e}")
    return {"status": "Success", "chart": chart}

@router.patch("/system/charts/{chart_id}")
async def update_chart(chart_id: str, req: ChartUpdateRequest, k: GridOSKernel = Depends(current_kernel_dep)):
    updates = req.model_dump(exclude={"sheet"}, exclude_none=True)
    try:
        chart = kernel.update_chart(chart_id, updates, sheet_name=req.sheet)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not update chart: {e}")
    return {"status": "Success", "chart": chart}

@router.delete("/system/charts/{chart_id}")
async def delete_chart(chart_id: str, sheet: Optional[str] = None, k: GridOSKernel = Depends(current_kernel_dep)):
    if not kernel.delete_chart(chart_id, sheet_name=sheet):
        raise HTTPException(status_code=404, detail=f"Chart '{chart_id}' not found.")
    return {"status": "Success"}
