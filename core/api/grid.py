"""
Grid routes - cell reads/writes, ranges, clearing.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/grid", tags=["grid"])

# ============ Models ============

class CellWriteRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    cell: str  # e.g., "A1"
    value: Any
    locked: bool = False


class RangeWriteRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    start_cell: str  # e.g., "A1"
    values: List[List[Any]]  # 2D array
    locked: bool = False


class RangeReadRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    range_str: str  # e.g., "A1:B10"


class ClearRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    range_str: Optional[str] = None  # If None, clear all


class FormatRequest(BaseModel):
    workbook_id: Optional[str] = None
    sheet: Optional[str] = None
    cell: str
    format_spec: Dict[str, Any]  # { "number_format": "currency", "bold": true, ... }


# ============ Routes ============

@router.post("/cell")
async def write_cell(req: CellWriteRequest):
    """
    Write a single cell value.
    
    Example:
    {
        "cell": "A1",
        "value": 100,
        "locked": false
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Cell write not yet migrated to modular structure"
    )


@router.post("/range")
async def write_range(req: RangeWriteRequest):
    """
    Write a rectangular range of values.
    
    Example:
    {
        "start_cell": "A1",
        "values": [
            ["Header1", "Header2"],
            [100, 200],
            [150, 250]
        ]
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Range write not yet migrated to modular structure"
    )


@router.post("/read")
async def read_range(req: RangeReadRequest):
    """
    Read values from a range.
    
    Returns:
    {
        "values": [["A", "B"], [1, 2]],
        "formulas": [[null, null], [null, null]]
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Range read not yet migrated to modular structure"
    )


@router.post("/clear")
async def clear_range(req: ClearRequest):
    """
    Clear cells in a range (or entire sheet if no range specified).
    """
    raise HTTPException(
        status_code=501,
        detail="Clear not yet migrated to modular structure"
    )


@router.post("/format")
async def format_cells(req: FormatRequest):
    """
    Apply formatting to a cell or range.
    
    Supported formats:
    - number_format: "currency", "percent", "decimal", "date"
    - bold, italic, underline: boolean
    - bg_color, text_color: hex color
    - alignment: "left", "center", "right"
    """
    raise HTTPException(
        status_code=501,
        detail="Format not yet migrated to modular structure"
    )


@router.get("/metadata")
async def get_grid_metadata(workbook_id: Optional[str] = None, sheet: Optional[str] = None):
    """
    Get metadata about the grid: dimensions, locked cells, etc.
    """
    raise HTTPException(
        status_code=501,
        detail="Metadata not yet migrated to modular structure"
    )
