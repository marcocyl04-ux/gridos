"""
Agent routes - AI-powered suggestions and writes.
Extracted from main.py for modularity.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/agent", tags=["agents"])

# ============ Models ============

class ChatRequest(BaseModel):
    workbook_id: Optional[str] = None
    agent_id: str = "default"
    message: str
    sheet: Optional[str] = None
    selected_cells: List[str] = []
    scope: str = "current_sheet"
    model_id: Optional[str] = None


class ExecuteGraphRequest(BaseModel):
    workbook_id: Optional[str] = None
    nodes: List[Dict[str, Any]]
    connections: List[Dict[str, Any]] = []
    variables: Dict[str, Any] = {}


# ============ Routes ============

@router.post("/chat")
async def agent_chat(req: ChatRequest):
    """
    Send a message to an agent and get a suggestion.
    
    Returns a preview of what the agent would write (no writes applied yet).
    The preview can be accepted, edited, or discarded.
    """
    # This is a stub - actual implementation lives in main.py for now
    # During restructuring, this will be moved here
    raise HTTPException(
        status_code=501,
        detail="Agent chat endpoint not yet migrated to modular structure"
    )


@router.post("/execute-graph")
async def execute_graph(req: ExecuteGraphRequest):
    """
    Execute a node graph workflow.
    
    This is the low-level API for running compositions of nodes:
    - QUERY: read from grid
    - FORMULA: compute expressions
    - CELL_WRITE: write values
    - CONDITIONAL: branch logic
    - AGGREGATE: sum, avg, etc
    
    Example:
    {
        "nodes": [
            {
                "id": "get_revenue",
                "node_type": "QUERY",
                "inputs": {"range": "A1:A12"}
            },
            {
                "id": "calc_growth",
                "node_type": "FORMULA",
                "inputs": {"values": "get_revenue.outputs.values", "formula": "..."}
            }
        ],
        "connections": [
            {"from": "get_revenue", "to": "calc_growth", "signal": "values"}
        ]
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Graph execution not yet migrated to modular structure"
    )


@router.post("/write")
async def agent_write(
    workbook_id: Optional[str] = None,
    agent_id: str = "default",
    intent: Dict[str, Any] = Body(...)
):
    """
    Apply an agent suggestion to the grid.
    
    Intent format:
    {
        "target_cell": "A1",
        "values": [["Header"], ["Value"]],
        "chart_spec": {...},  # optional
        "macro_spec": {...}   # optional
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Agent write not yet migrated to modular structure"
    )


@router.post("/write/graph")
async def agent_write_graph(
    workbook_id: Optional[str] = None,
    graph: ExecuteGraphRequest = Body(...)
):
    """
    Execute a graph and apply all writes atomically.
    """
    raise HTTPException(
        status_code=501,
        detail="Graph write not yet migrated to modular structure"
    )


@router.post("/chat/chain")
async def agent_chat_chain(
    workbook_id: Optional[str] = None,
    agent_id: str = "default",
    messages: List[Dict[str, str]] = Body(...)
):
    """
    Multi-turn agent conversation with memory.
    
    Each message in the chain can reference previous outputs.
    Useful for iterative refinement of financial models.
    """
    raise HTTPException(
        status_code=501,
        detail="Chat chain not yet migrated to modular structure"
    )
