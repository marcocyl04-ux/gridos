"""
GridOS API — Grid endpoints.

Handles: /grid/cell, /grid/range, /grid/clear, /grid/format
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.engine import GridOSKernel

from .deps import (
    current_kernel_dep,
    kernel,
    CellUpdateRequest,
    RangeUpdateRequest,
    CellClearRequest,
    CellFormatRequest,
)

router = APIRouter()


@router.post("/grid/cell")
async def update_cell(
    req: CellUpdateRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    try:
        target = kernel.write_user_cell(req.cell.upper(), req.value, user_id="User", sheet_name=req.sheet)
        return {"status": "Success", "cell": target, "sheet": req.sheet or kernel.active_sheet}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/grid/range")
async def update_range(
    req: RangeUpdateRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    try:
        target = kernel.write_user_range(req.target_cell.upper(), req.values, user_id="User", sheet_name=req.sheet)
        return {"status": "Success", "target": target, "sheet": req.sheet or kernel.active_sheet}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/grid/clear")
async def clear_cells(
    req: CellClearRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    if not req.cells:
        return {"status": "Success", "cleared": 0, "skipped_locked": 0}
    result = kernel.clear_cells(req.cells, sheet_name=req.sheet)
    return {"status": "Success", **result, "sheet": req.sheet or kernel.active_sheet}


@router.post("/grid/format")
async def set_cell_format(
    req: CellFormatRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    decimals = req.decimals
    if decimals is not None:
        if not isinstance(decimals, int) or decimals < 0 or decimals > 30:
            raise HTTPException(status_code=400, detail="decimals must be an integer between 0 and 30, or null to reset")
    updated = []
    for cell_a1 in req.cells:
        try:
            updated.append(kernel.set_cell_format(cell_a1.upper(), decimals, sheet_name=req.sheet))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "Success", "updated": updated, "sheet": req.sheet or kernel.active_sheet}
