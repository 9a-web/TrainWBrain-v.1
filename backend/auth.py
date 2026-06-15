"""
Authentication utilities for TrainWithBrain.

Three login methods, one unified session model:
  1. Telegram WebApp  — validate initData HMAC with the bot token (one-tap).
  2. Email + password — register/login, bcrypt password hashing.
  3. Google           — Emergent Managed Google Auth (keyless): exchange a
                        session_id for the user's profile, then create our session.

Every account is keyed by `telegram_id` (real for Telegram users, synthetic for
email/Google accounts) so all existing plan/session logic keeps working unchanged.

Sessions are opaque random tokens stored in the `user_sessions` collection and
checked on every request (Authorization: Bearer <token>  OR  session_token cookie).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qsl

import httpx
from passlib.context import CryptContext
from pydantic import BaseModel

SESSION_TTL_DAYS = 7
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class RegisterReq(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginReq(BaseModel):
    email: str
    password: str


class TelegramAuthReq(BaseModel):
    init_data: str


class GoogleSessionReq(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; truncate defensively.
    return pwd_context.hash(password[:72])


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password[:72], password_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)


def synthetic_telegram_id() -> int:
    """Stable-but-unique pseudo telegram_id for non-Telegram accounts.

    Real Telegram ids are well below this range, so collisions are practically
    impossible; callers still re-roll on the rare clash."""
    return 900_000_000_000 + secrets.randbelow(99_999_999_999)


# ---------------------------------------------------------------------------
# Telegram WebApp initData validation (HMAC-SHA256 per Telegram docs)
# ---------------------------------------------------------------------------
def validate_telegram_init_data(init_data: str, bot_token: str, max_age_sec: int = 86400) -> Optional[dict]:
    """Return the parsed initData dict if the signature is valid, else None."""
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc_hash, received_hash):
            return None
        # Optional freshness check (ignore if auth_date missing/unparseable)
        auth_date = parsed.get("auth_date")
        if auth_date and max_age_sec:
            try:
                ts = int(auth_date)
                if (datetime.now(timezone.utc).timestamp() - ts) > max_age_sec:
                    return None
            except Exception:
                pass
        return parsed
    except Exception:
        return None


def parse_telegram_user(parsed: dict) -> Optional[dict]:
    """Extract the `user` JSON object from validated initData."""
    raw = parsed.get("user")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Emergent Managed Google Auth — exchange session_id for profile + token
# ---------------------------------------------------------------------------
async def exchange_emergent_session(session_id: str) -> Optional[dict]:
    """Returns {id, email, name, picture, session_token} or None."""
    if not session_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id})
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------
async def ensure_auth_indexes(db) -> None:
    await db.users.create_index("email", unique=True, sparse=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("telegram_id")
