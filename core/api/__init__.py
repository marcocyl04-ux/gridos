"""
GridOS API modules - organized by domain.
Each module exports its routes to be mounted in main.py.
"""

from .agents import router as agents_router
from .grid import router as grid_router
from .templates import router as templates_router
from .workbooks import router as workbooks_router
from .system import router as system_router

__all__ = [
    'agents_router',
    'grid_router', 
    'templates_router',
    'workbooks_router',
    'system_router'
]
