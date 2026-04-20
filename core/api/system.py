"""
System routes - health, auth, config.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(tags=["system"])

# ============ Models ============

class HealthStatus(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    services: Dict[str, str]  # "database": "ok", "llm": "ok", etc


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    auth_provider: str  # "supabase", "google", "email"
    created_at: str


class SystemConfig(BaseModel):
    mode: str  # "oss" or "saas"
    features: Dict[str, bool]
    llm_providers: Dict[str, bool]


# ============ Routes ============

@router.get("/healthz")
async def health_check():
    """
    Simple health check.
    
    Returns:
    {
        "status": "ok",
        "timestamp": "2024-01-20T15:00:00Z"
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Health check not yet migrated to modular structure"
    )


@router.get("/auth/whoami")
async def get_current_user():
    """
    Get current authenticated user info.
    
    Returns:
    {
        "id": "user-uuid",
        "email": "user@example.com",
        "name": "John Doe",
        "auth_provider": "supabase"
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Auth check not yet migrated to modular structure"
    )


@router.get("/cloud/status")
async def get_cloud_status():
    """
    Get cloud deployment status (SaaS mode, features, etc).
    
    Returns:
    {
        "mode": "saas",
        "features": {
            "multi_user": true,
            "templates": true,
            "api_keys": true
        },
        "client_config": {
            "supabase_url": "https://...",
            "supabase_anon_key": "..."
        }
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Cloud status not yet migrated to modular structure"
    )


@router.post("/auth/login")
async def login(email: str, password: str):
    """
    Authenticate user (email/password or SSO).
    """
    raise HTTPException(
        status_code=501,
        detail="Login not yet migrated to modular structure"
    )


@router.post("/auth/logout")
async def logout():
    """
    Logout current user.
    """
    raise HTTPException(
        status_code=501,
        detail="Logout not yet migrated to modular structure"
    )


@router.post("/auth/signup")
async def signup(email: str, password: str, name: str):
    """
    Create new user account.
    """
    raise HTTPException(
        status_code=501,
        detail="Signup not yet migrated to modular structure"
    )


@router.get("/settings")
async def get_settings():
    """
    Get user settings.
    """
    raise HTTPException(
        status_code=501,
        detail="Settings not yet migrated to modular structure"
    )


@router.post("/settings/keys/save")
async def save_api_keys(keys: Dict[str, str]):
    """
    Save API keys for LLM providers.
    
    Example:
    {
        "openrouter": "sk-...",
        "anthropic": "sk-ant-...",
        "google": "..."
    }
    """
    raise HTTPException(
        status_code=501,
        detail="Key save not yet migrated to modular structure"
    )


@router.get("/debug/grid")
async def debug_grid(workbook_id: Optional[str] = None):
    """
    Debug endpoint to inspect grid state (development only).
    """
    raise HTTPException(
        status_code=501,
        detail="Debug endpoint not yet migrated to modular structure"
    )
