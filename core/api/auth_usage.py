"""Auth and usage endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.api.deps import cloud_config, AuthUser, require_user

router = APIRouter()


@router.get("/auth/whoami")
async def whoami(user: AuthUser = Depends(require_user)):
    return {"id": user.id, "email": user.email, "mode": "saas" if cloud_config.SAAS_MODE else "oss"}


@router.get("/usage/me")
async def usage_me(user: AuthUser = Depends(require_user)):
    if not cloud_config.SAAS_MODE:
        return {
            "mode": "oss", "email": None, "tier": "oss", "joined_at": None,
            "month": datetime.now(timezone.utc).strftime("%Y-%m-01"),
            "total_tokens": 0, "cost_cents": 0, "tier_limit": 0,
            "tokens_remaining": None, "quota_pct": 0,
        }
    if not cloud_config.SAAS_FEATURES["usage_tracking"].enabled:
        raise HTTPException(status_code=503, detail="Usage tracking is not configured.")
    try:
        from supabase import create_client
    except ImportError as e:
        raise HTTPException(status_code=503, detail="supabase-py is not installed.") from e

    client = create_client(cloud_config.SUPABASE_URL, cloud_config.SUPABASE_SERVICE_ROLE_KEY)
    month_str = datetime.now(timezone.utc).strftime("%Y-%m-01")
    tier, joined_at = "free", None
    try:
        u = client.table("users").select("subscription_tier, created_at").eq("id", user.id).limit(1).execute()
        if u.data:
            tier = u.data[0].get("subscription_tier") or "free"
            joined_at = u.data[0].get("created_at")
    except Exception:
        pass
    total_tokens, cost_cents = 0, 0
    try:
        usage = client.table("user_usage").select("total_tokens, cost_cents").eq("user_id", user.id).eq("month", month_str).limit(1).execute()
        if usage.data:
            total_tokens = int(usage.data[0].get("total_tokens") or 0)
            cost_cents = int(usage.data[0].get("cost_cents") or 0)
    except Exception:
        pass
    limit = cloud_config.tier_limit(tier)
    remaining = max(0, limit - total_tokens) if limit > 0 else None
    pct = min(100, int(round((total_tokens / limit) * 100))) if limit > 0 else 0
    return {
        "mode": "saas", "email": user.email, "tier": tier, "joined_at": joined_at,
        "month": month_str, "total_tokens": total_tokens, "cost_cents": cost_cents,
        "tier_limit": limit, "tokens_remaining": remaining, "quota_pct": pct,
    }
