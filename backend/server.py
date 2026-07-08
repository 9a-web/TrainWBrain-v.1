from fastapi import FastAPI, APIRouter, HTTPException, Body, Depends, Header, Cookie, Response, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import asyncio
import logging
import re
import copy
import json
import secrets
import difflib
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, date, timedelta
import httpx

from models import (
    Exercise, ExerciseCreate,
    ProgramTemplate, ProgramTemplateCreate, ProgramTemplateUpdate,
    Plan, PlanCreate,
    WorkoutSession, SessionStartReq,
    CoachLink,
    PlanDayMark, DaySkipReq, DayRescheduleReq, DayMarkReq, UserSettingsReq,
)
from seed import (
    seed_builtins, ensure_indexes,
    group_letters, muscle_letter, percent_of, scheme_tonnage,
)
from auth import (
    RegisterReq, LoginReq, TelegramAuthReq, GoogleSessionReq, GoogleOAuthReq,
    hash_password, verify_password, new_session_token, session_expiry,
    synthetic_telegram_id, validate_telegram_init_data, parse_telegram_user,
    exchange_emergent_session, exchange_google_code, ensure_auth_indexes,
)
from realtime import manager, now_iso as rt_now


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Google OAuth (own credentials — shows the app's own consent-screen branding)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str


# User Models
class UserCreate(BaseModel):
    """Данные пользователя из Telegram WebApp"""
    telegram_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class User(BaseModel):
    """Модель пользователя в БД"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


# User endpoints
@api_router.post("/users", response_model=User)
async def create_or_update_user(user_data: UserCreate):
    """
    Создать или обновить пользователя (upsert).
    Вызывается при каждом входе в Telegram WebApp.
    """
    existing_user = await db.users.find_one(
        {"telegram_id": user_data.telegram_id},
        {"_id": 0}
    )
    
    if existing_user:
        # Обновляем существующего пользователя
        update_data = {
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "username": user_data.username,
            "language_code": user_data.language_code,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.update_one(
            {"telegram_id": user_data.telegram_id},
            {"$set": update_data}
        )
        # Получаем обновлённого пользователя
        updated_user = await db.users.find_one(
            {"telegram_id": user_data.telegram_id},
            {"_id": 0}
        )
        # Конвертируем даты
        for field in ['created_at', 'updated_at']:
            if isinstance(updated_user.get(field), str):
                updated_user[field] = datetime.fromisoformat(updated_user[field])
        logger.info(f"User updated: telegram_id={user_data.telegram_id}")
        return updated_user
    else:
        # Создаём нового пользователя
        new_user = User(
            telegram_id=user_data.telegram_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username,
            language_code=user_data.language_code
        )
        doc = new_user.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        
        await db.users.insert_one(doc)
        logger.info(f"New user created: telegram_id={user_data.telegram_id}, id={new_user.id}")
        return new_user


@api_router.get("/users/{telegram_id}", response_model=User)
async def get_user(telegram_id: int):
    """Получить пользователя по Telegram ID"""
    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"_id": 0}
    )
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    
    # Конвертируем даты
    for field in ['created_at', 'updated_at']:
        if isinstance(user.get(field), str):
            user[field] = datetime.fromisoformat(user[field])
    return user


# ===========================================================================
# P3 — Режим пользователя (athlete/coach), приглашения, подопечные, видимость плана
# ===========================================================================
import secrets as _secrets

_BOT_USERNAME_CACHE = {"value": None}


class ModeReq(BaseModel):
    mode: str  # athlete | coach


class CoachInviteReq(BaseModel):
    coach_telegram_id: int


class CoachLinkReq(BaseModel):
    code: str
    athlete_telegram_id: int


class CoachUnlinkReq(BaseModel):
    athlete_telegram_id: int


class VisibilityReq(BaseModel):
    visibility: str  # draft | published


class WeekPublishReq(BaseModel):
    published: bool = True


class TrainingDaysReq(BaseModel):
    training_days: List[int] = Field(default_factory=list)


def _gen_invite_code(n: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без неоднозначных символов
    return "".join(_secrets.choice(alphabet) for _ in range(n))


async def _unique_invite_code() -> str:
    code = _gen_invite_code()
    while await db.users.find_one({"invite_code": code}, {"_id": 0}):
        code = _gen_invite_code()
    return code


async def _get_bot_username() -> Optional[str]:
    """Best-effort: получить username бота через getMe (кэшируется)."""
    if _BOT_USERNAME_CACHE["value"] is not None:
        return _BOT_USERNAME_CACHE["value"] or None
    if not TELEGRAM_BOT_TOKEN:
        _BOT_USERNAME_CACHE["value"] = ""
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as cx:
            r = await cx.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
            if r.status_code == 200:
                uname = (r.json().get("result") or {}).get("username")
                _BOT_USERNAME_CACHE["value"] = uname or ""
                return uname
    except Exception:
        pass
    _BOT_USERNAME_CACHE["value"] = ""
    return None


def _user_brief(u: Optional[dict]) -> Optional[dict]:
    if not u:
        return None
    return {
        "telegram_id": u.get("telegram_id"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "username": u.get("username"),
        "picture": u.get("picture"),
        "roles": u.get("roles") or ["athlete"],
        "active_mode": u.get("active_mode") or "athlete",
    }


@api_router.patch("/users/{telegram_id}/mode")
async def switch_user_mode(telegram_id: int, payload: ModeReq):
    """Переключить активный режим UI (athlete/coach). При первом переходе в coach —
    добавляет роль coach и генерирует invite_code."""
    mode = (payload.mode or "").strip().lower()
    if mode not in ("athlete", "coach"):
        raise HTTPException(status_code=400, detail="mode должен быть athlete или coach")
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles = set(user.get("roles") or ["athlete"])
    roles.add("athlete")
    set_fields = {"active_mode": mode, "updated_at": datetime.now(timezone.utc).isoformat()}
    if mode == "coach":
        roles.add("coach")
        if not user.get("invite_code"):
            set_fields["invite_code"] = await _unique_invite_code()
    set_fields["roles"] = sorted(roles)
    await db.users.update_one({"telegram_id": telegram_id}, {"$set": set_fields})
    updated = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0, "password_hash": 0})
    return updated


# ===========================================================================
# Аутентификация: Telegram (один тап) + Email/пароль + Google (Emergent Auth)
# Единая модель сессий (коллекция user_sessions). Каждый аккаунт имеет
# telegram_id (реальный или синтетический) — ключ всех данных приложения.
# ===========================================================================

def _token_from(authorization, session_token):
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return session_token


async def _create_session(telegram_id: int, method: str) -> str:
    token = new_session_token()
    await db.user_sessions.insert_one({
        "session_token": token,
        "telegram_id": telegram_id,
        "auth_method": method,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": session_expiry().isoformat(),
    })
    return token


async def _user_public(telegram_id: int) -> dict:
    return await db.users.find_one(
        {"telegram_id": telegram_id},
        {"_id": 0, "password_hash": 0},
    )


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token", value=token,
        max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="none", path="/",
    )


async def _unique_synth_id() -> int:
    tgid = synthetic_telegram_id()
    while await db.users.find_one({"telegram_id": tgid}, {"_id": 0}):
        tgid = synthetic_telegram_id()
    return tgid


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    session_token: Optional[str] = Cookie(default=None),
):
    token = _token_from(authorization, session_token)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Недействительная сессия")
    exp = sess.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Сессия истекла")
    user = await db.users.find_one(
        {"telegram_id": sess["telegram_id"]},
        {"_id": 0, "password_hash": 0},
    )
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


@api_router.post("/auth/register")
async def auth_register(payload: RegisterReq, response: Response):
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 6 символов")
    if await db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    tgid = await _unique_synth_id()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()), "telegram_id": tgid,
        "first_name": (payload.name or email.split("@")[0]).strip(),
        "last_name": None, "username": None, "language_code": "ru",
        "email": email, "password_hash": hash_password(payload.password),
        "auth_provider": ["email"], "picture": None,
        "created_at": now, "updated_at": now,
    }
    await db.users.insert_one(doc)
    token = await _create_session(tgid, "email")
    _set_session_cookie(response, token)
    logger.info(f"Auth register: email={email}, telegram_id={tgid}")
    return {"token": token, "user": await _user_public(tgid)}


@api_router.post("/auth/login")
async def auth_login(payload: LoginReq, response: Response):
    email = (payload.email or "").strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = await _create_session(user["telegram_id"], "email")
    _set_session_cookie(response, token)
    return {"token": token, "user": await _user_public(user["telegram_id"])}


@api_router.post("/auth/telegram")
async def auth_telegram(payload: TelegramAuthReq, response: Response):
    parsed = validate_telegram_init_data(payload.init_data, TELEGRAM_BOT_TOKEN)
    if not parsed:
        raise HTTPException(status_code=401, detail="Не удалось проверить подпись Telegram")
    tg_user = parse_telegram_user(parsed)
    if not tg_user or "id" not in tg_user:
        raise HTTPException(status_code=401, detail="Нет данных пользователя Telegram")
    tgid = int(tg_user["id"])
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.users.find_one({"telegram_id": tgid}, {"_id": 0})
    if existing:
        await db.users.update_one({"telegram_id": tgid}, {
            "$set": {
                "first_name": tg_user.get("first_name") or existing.get("first_name") or "User",
                "last_name": tg_user.get("last_name"),
                "username": tg_user.get("username"),
                "language_code": tg_user.get("language_code") or existing.get("language_code") or "ru",
                "updated_at": now,
            },
            "$addToSet": {"auth_provider": "telegram"},
        })
    else:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "telegram_id": tgid,
            "first_name": tg_user.get("first_name") or "User",
            "last_name": tg_user.get("last_name"),
            "username": tg_user.get("username"),
            "language_code": tg_user.get("language_code") or "ru",
            "email": None, "password_hash": None,
            "auth_provider": ["telegram"], "picture": tg_user.get("photo_url"),
            "created_at": now, "updated_at": now,
        })
    token = await _create_session(tgid, "telegram")
    _set_session_cookie(response, token)
    logger.info(f"Auth telegram: telegram_id={tgid}")
    return {"token": token, "user": await _user_public(tgid)}


@api_router.post("/auth/google/session")
async def auth_google_session(payload: GoogleSessionReq, response: Response):
    data = await exchange_emergent_session(payload.session_id)
    if not data or not data.get("email"):
        raise HTTPException(status_code=401, detail="Не удалось авторизоваться через Google")
    email = data["email"].strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        tgid = existing["telegram_id"]
        await db.users.update_one({"telegram_id": tgid}, {
            "$set": {
                "first_name": existing.get("first_name") or data.get("name") or email.split("@")[0],
                "picture": data.get("picture") or existing.get("picture"),
                "updated_at": now,
            },
            "$addToSet": {"auth_provider": "google"},
        })
    else:
        tgid = await _unique_synth_id()
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "telegram_id": tgid,
            "first_name": data.get("name") or email.split("@")[0],
            "last_name": None, "username": None, "language_code": "ru",
            "email": email, "password_hash": None,
            "auth_provider": ["google"], "google_sub": data.get("id"),
            "picture": data.get("picture"),
            "created_at": now, "updated_at": now,
        })
    # Persist the Emergent-issued session_token if present, else our own.
    token = data.get("session_token") or new_session_token()
    await db.user_sessions.insert_one({
        "session_token": token, "telegram_id": tgid, "auth_method": "google",
        "created_at": now, "expires_at": session_expiry().isoformat(),
    })
    _set_session_cookie(response, token)
    logger.info(f"Auth google: email={email}, telegram_id={tgid}")
    return {"token": token, "user": await _user_public(tgid)}


@api_router.get("/auth/google/config")
async def auth_google_config():
    """Public Google OAuth config for the frontend (client_id is not secret)."""
    return {"client_id": GOOGLE_CLIENT_ID}


@api_router.post("/auth/google/oauth")
async def auth_google_oauth(payload: GoogleOAuthReq, response: Response):
    """Direct Google OAuth (own credentials): exchange the authorization code
    for the user's profile, then create/load the account and issue our session."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth не настроен на сервере")
    data = await exchange_google_code(
        payload.code, payload.redirect_uri, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    )
    if not data or not data.get("email"):
        raise HTTPException(status_code=401, detail="Не удалось авторизоваться через Google")
    email = data["email"].strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        tgid = existing["telegram_id"]
        await db.users.update_one({"telegram_id": tgid}, {
            "$set": {
                "first_name": existing.get("first_name") or data.get("name") or email.split("@")[0],
                "picture": data.get("picture") or existing.get("picture"),
                "updated_at": now,
            },
            "$addToSet": {"auth_provider": "google"},
        })
    else:
        tgid = await _unique_synth_id()
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "telegram_id": tgid,
            "first_name": data.get("name") or email.split("@")[0],
            "last_name": None, "username": None, "language_code": "ru",
            "email": email, "password_hash": None,
            "auth_provider": ["google"], "google_sub": data.get("sub"),
            "picture": data.get("picture"),
            "created_at": now, "updated_at": now,
        })
    token = await _create_session(tgid, "google")
    _set_session_cookie(response, token)
    logger.info(f"Auth google-oauth: email={email}, telegram_id={tgid}")
    return {"token": token, "user": await _user_public(tgid)}


@api_router.get("/auth/me")
async def auth_me(current=Depends(get_current_user)):
    return current


@api_router.post("/auth/logout")
async def auth_logout(
    response: Response,
    authorization: Optional[str] = Header(default=None),
    session_token: Optional[str] = Cookie(default=None),
):
    token = _token_from(authorization, session_token)
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api_router.get("/telegram/avatar/{user_id}")
async def get_telegram_avatar(user_id: int):
    """
    Получить URL аватарки пользователя Telegram через Bot API.
    Возвращает JSON с avatar_url.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not configured")
        return {"avatar_url": None, "error": "Bot token not configured"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            # 1. Получаем фото профиля пользователя через Bot API
            photos_response = await http_client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUserProfilePhotos",
                params={"user_id": user_id, "limit": 1}
            )
            photos_data = photos_response.json()
            
            if not photos_data.get("ok"):
                logger.warning(f"Telegram API error: {photos_data.get('description', 'Unknown error')}")
                return {"avatar_url": None, "error": photos_data.get("description")}
            
            photos = photos_data.get("result", {}).get("photos", [])
            if not photos:
                # У пользователя нет фото профиля
                return {"avatar_url": None, "message": "User has no profile photo"}
            
            # 2. Берём самое большое фото (последнее в массиве размеров)
            photo_sizes = photos[0]
            largest_photo = photo_sizes[-1]  # Последний = самый большой
            file_id = largest_photo["file_id"]
            
            # 3. Получаем путь к файлу
            file_response = await http_client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
                params={"file_id": file_id}
            )
            file_data = file_response.json()
            
            if not file_data.get("ok"):
                logger.warning(f"Failed to get file path: {file_data.get('description')}")
                return {"avatar_url": None, "error": file_data.get("description")}
            
            file_path = file_data["result"]["file_path"]
            
            # 4. Формируем прямой URL к файлу
            avatar_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            
            return {
                "avatar_url": avatar_url,
                "file_id": file_id,
                "width": largest_photo.get("width"),
                "height": largest_photo.get("height")
            }
            
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching Telegram avatar for user {user_id}")
        return {"avatar_url": None, "error": "Request timeout"}
    except Exception as e:
        logger.error(f"Error fetching Telegram avatar for user {user_id}: {e}")
        return {"avatar_url": None, "error": str(e)}

# ===========================================================================
# PHASE 1 — Программы и Планы
# ===========================================================================

# ---- Справочник упражнений ----
@api_router.get("/exercises", response_model=List[Exercise])
async def list_exercises(query: Optional[str] = None, muscle: Optional[str] = None, owner: Optional[int] = None):
    filt = {}
    if query:
        filt["name"] = {"$regex": query, "$options": "i"}
    if muscle:
        filt["muscle_groups"] = muscle
    if owner is not None:
        filt["$or"] = [{"is_builtin": True}, {"owner_telegram_id": owner}]
    else:
        # по умолчанию отдаём встроенные упражнения
        filt["is_builtin"] = True
    docs = await db.exercises.find(filt, {"_id": 0}).to_list(1000)
    return docs


@api_router.post("/exercises", response_model=Exercise)
async def create_exercise(payload: ExerciseCreate):
    ex = Exercise(**payload.model_dump(), is_builtin=False)
    doc = ex.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.exercises.insert_one(doc)
    logger.info(f"Custom exercise created: {ex.name} (owner={ex.owner_telegram_id})")
    return ex


# ---- Шаблоны программ (библиотека / конструктор / импорт / шаринг) ----
_SHARE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _new_share_code():
    return "TWB-" + "".join(secrets.choice(_SHARE_ALPHABET) for _ in range(6))


_bot_username_cache = {"value": None, "checked": False}


async def _get_bot_username():
    """Username бота (для deep-link t.me/<bot>?startapp=...). Ленивый кэш getMe."""
    if _bot_username_cache["checked"]:
        return _bot_username_cache["value"]
    _bot_username_cache["checked"] = True
    if not TELEGRAM_BOT_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
            d = r.json()
            if d.get("ok"):
                _bot_username_cache["value"] = (d.get("result") or {}).get("username")
    except Exception:
        pass
    return _bot_username_cache["value"]


def _template_recount(doc):
    """Пересчёт производных полей шаблона (weeks_count / days_per_week)."""
    weeks = doc.get("weeks") or []
    doc["weeks_count"] = len(weeks)
    dpw = 0
    for w in weeks:
        n = len([d for d in (w.get("days") or []) if not d.get("is_rest")])
        dpw = max(dpw, n)
    if dpw:
        doc["days_per_week"] = dpw
    return doc


def _template_exercise_count(doc):
    total = 0
    for w in (doc.get("weeks") or []):
        for d in (w.get("days") or []):
            total += len(d.get("exercises") or [])
    return total


def _template_first_week_preview(doc):
    """Компактное превью 1-й недели: карточки дней со списком упражнений."""
    weeks = doc.get("weeks") or []
    if not weeks:
        return []
    days = weeks[0].get("days") or []
    out = []
    for d in days:
        if d.get("is_rest"):
            continue
        exs = []
        for e in (d.get("exercises") or [])[:12]:
            scheme = [
                {"weight": s.get("weight"), "sets": s.get("sets"), "reps": s.get("reps")}
                for s in (e.get("sets_scheme") or [])
            ]
            exs.append({
                "name": e.get("exercise_name") or "",
                "muscle_group": e.get("muscle_group"),
                "lift_group": e.get("lift_group"),
                "is_accessory": bool(e.get("is_accessory")),
                "target_sets": e.get("target_sets"),
                "target_reps": e.get("target_reps"),
                "sets_scheme": scheme,
            })
        out.append({
            "day_index": d.get("day_index"),
            "title": d.get("title") or "",
            "exercises": exs,
        })
    return out


def _template_forecast(doc):
    """Прогноз прогресса. Для программ в кг — тоннаж по неделям + рост %.
    Для программ на %1ПМ (requires_maxes=True) — интенсивность (доля от base_max
    основного движения) по неделям.
    """
    weeks = doc.get("weeks") or []
    is_percent = bool(doc.get("requires_maxes"))
    base = doc.get("base_maxes") or {}
    weekly_tonnage = []
    weekly_intensity = []
    for idx, w in enumerate(weeks):
        wi = int(w.get("week_index") or (idx + 1))
        tonnage = 0.0
        pct_top = 0.0
        pct_sum = 0.0
        pct_n = 0
        for d in (w.get("days") or []):
            if d.get("is_rest"):
                continue
            for e in (d.get("exercises") or []):
                lg = e.get("lift_group")
                base_max = base.get(lg) if lg else None
                for s in (e.get("sets_scheme") or []):
                    try:
                        w_val = float(s.get("weight") or 0)
                        n_sets = int(s.get("sets") or 0)
                        reps = int(s.get("reps") or 0)
                    except (TypeError, ValueError):
                        continue
                    if w_val and n_sets and reps:
                        tonnage += w_val * n_sets * reps
                    if is_percent and lg and w_val:
                        bm = float(base_max) if base_max else 100.0
                        pct = (w_val / bm) * 100.0 if bm else 0.0
                        if pct > 0:
                            pct_top = max(pct_top, pct)
                            pct_sum += pct
                            pct_n += 1
        weekly_tonnage.append({"week": wi, "tonnage": round(tonnage, 1)})
        if is_percent:
            weekly_intensity.append({
                "week": wi,
                "top_percent": round(pct_top, 1),
                "avg_percent": round(pct_sum / pct_n, 1) if pct_n else 0.0,
            })

    if is_percent:
        non_empty = [x for x in weekly_intensity if x["top_percent"] > 0]
        first_p = non_empty[0]["top_percent"] if non_empty else None
        last_p = non_empty[-1]["top_percent"] if non_empty else None
        growth = round(last_p - first_p, 1) if (first_p is not None and last_p is not None) else None
        return {
            "is_percent_based": True,
            "weekly_intensity": weekly_intensity,
            "first_percent": first_p,
            "last_percent": last_p,
            "growth_points": growth,
        }

    non_empty = [x for x in weekly_tonnage if x["tonnage"] > 0]
    first_t = non_empty[0]["tonnage"] if non_empty else None
    last_t = non_empty[-1]["tonnage"] if non_empty else None
    growth = None
    if first_t and last_t is not None:
        growth = round((last_t - first_t) / first_t * 100, 1)
    return {
        "is_percent_based": False,
        "weekly_tonnage": weekly_tonnage,
        "first_tonnage": first_t,
        "last_tonnage": last_t,
        "growth_pct": growth,
    }


async def _get_own_template_or_403(template_id: str, current: dict):
    doc = await db.programs.find_one({"id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    if doc.get("is_builtin") or doc.get("owner_telegram_id") != current.get("telegram_id"):
        raise HTTPException(status_code=403, detail="Можно изменять только свои программы")
    return doc


@api_router.get("/programs/templates", response_model=List[ProgramTemplate])
async def list_templates(level: Optional[str] = None, goal: Optional[str] = None,
                         current: dict = Depends(get_current_user)):
    filt = {"$or": [{"is_builtin": True}, {"owner_telegram_id": current.get("telegram_id")}]}
    if level:
        filt["level"] = level
    if goal:
        filt["goal"] = goal
    docs = await db.programs.find(filt, {"_id": 0}).to_list(1000)
    docs.sort(key=lambda t: (not t.get("is_builtin"), t.get("created_at") or ""))
    return docs


@api_router.get("/programs/templates/{template_id}", response_model=ProgramTemplate)
async def get_template(template_id: str, current: dict = Depends(get_current_user)):
    doc = await db.programs.find_one({"id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    if not doc.get("is_builtin") and doc.get("owner_telegram_id") != current.get("telegram_id"):
        raise HTTPException(status_code=403, detail="Нет доступа к этой программе")
    return doc


@api_router.post("/programs/templates", response_model=ProgramTemplate)
async def create_template(payload: ProgramTemplateCreate,
                          current: dict = Depends(get_current_user)):
    tpl = ProgramTemplate(
        **{**payload.model_dump(), "owner_telegram_id": current.get("telegram_id")},
        is_builtin=False,
    )
    doc = tpl.model_dump()
    if not doc.get("source"):
        doc["source"] = "constructor"
    _template_recount(doc)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.programs.insert_one(dict(doc))
    logger.info(f"Custom template created: {tpl.name} (owner={current.get('telegram_id')})")
    return doc


@api_router.patch("/programs/templates/{template_id}", response_model=ProgramTemplate)
async def update_template(template_id: str, payload: ProgramTemplateUpdate,
                          current: dict = Depends(get_current_user)):
    doc = await _get_own_template_or_403(template_id, current)
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    doc.update(upd)
    _template_recount(doc)
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.programs.update_one({"id": template_id}, {"$set": {k: doc[k] for k in
        list(upd.keys()) + ["weeks_count", "days_per_week", "updated_at"] if k in doc}})
    return doc


@api_router.delete("/programs/templates/{template_id}")
async def delete_template(template_id: str, current: dict = Depends(get_current_user)):
    await _get_own_template_or_403(template_id, current)
    res = await db.programs.delete_one({"id": template_id})
    return {"deleted": res.deleted_count}


@api_router.post("/programs/templates/{template_id}/share")
async def share_template(template_id: str, current: dict = Depends(get_current_user)):
    """Владелец получает короткий код и ссылки для шаринга программы."""
    doc = await _get_own_template_or_403(template_id, current)
    code = doc.get("share_code")
    if not code:
        for _ in range(10):
            code = _new_share_code()
            if not await db.programs.find_one({"share_code": code}, {"_id": 0, "id": 1}):
                break
        await db.programs.update_one({"id": template_id}, {"$set": {
            "share_code": code, "updated_at": datetime.now(timezone.utc).isoformat()}})
    bot = await _get_bot_username()
    return {
        "code": code,
        "web_path": f"/import/{code}",
        "tg_link": f"https://t.me/{bot}?startapp=import_{code.replace('-', '_')}" if bot else None,
    }


@api_router.get("/programs/shared/{code}")
async def get_shared_program(code: str):
    """ПУБЛИЧНОЕ превью программы по коду (для landing-страницы ссылки)."""
    norm = code.strip().upper().replace("_", "-")
    if not norm.startswith("TWB-"):
        norm = f"TWB-{norm}"
    doc = await db.programs.find_one({"share_code": norm}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Программа по этому коду не найдена")
    owner = await db.users.find_one(
        {"telegram_id": doc.get("owner_telegram_id")}, {"_id": 0, "first_name": 1})
    bot = await _get_bot_username()
    return {
        "code": norm,
        "name": doc.get("name"),
        "description": doc.get("description") or "",
        "level": doc.get("level"),
        "goal": doc.get("goal"),
        "weeks_count": doc.get("weeks_count") or len(doc.get("weeks") or []),
        "days_per_week": doc.get("days_per_week"),
        "exercises_count": _template_exercise_count(doc),
        "requires_maxes": bool(doc.get("requires_maxes")),
        "author_name": (owner or {}).get("first_name") or doc.get("author") or "Пользователь TWB",
        "week1_days": _template_first_week_preview(doc),
        "forecast": _template_forecast(doc),
        "tg_link": f"https://t.me/{bot}?startapp=import_{norm.replace('-', '_')}" if bot else None,
    }


@api_router.post("/programs/import/{code}")
async def import_shared_program(code: str, current: dict = Depends(get_current_user)):
    """Импорт программы по коду — копия появляется в «Моих программах»."""
    norm = code.strip().upper().replace("_", "-")
    if not norm.startswith("TWB-"):
        norm = f"TWB-{norm}"
    src = await db.programs.find_one({"share_code": norm}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Программа по этому коду не найдена")
    tgid = current.get("telegram_id")
    if src.get("owner_telegram_id") == tgid:
        return {"template": src, "already_imported": True, "own": True}
    existing = await db.programs.find_one(
        {"owner_telegram_id": tgid, "shared_from": src["id"]}, {"_id": 0})
    if existing:
        return {"template": existing, "already_imported": True, "own": False}
    owner = await db.users.find_one(
        {"telegram_id": src.get("owner_telegram_id")}, {"_id": 0, "first_name": 1})
    now = datetime.now(timezone.utc).isoformat()
    new_doc = {
        **src,
        "id": str(uuid.uuid4()),
        "slug": None,
        "is_builtin": False,
        "owner_telegram_id": tgid,
        "source": "import",
        "shared_from": src["id"],
        "share_code": None,
        "author": src.get("author") or (owner or {}).get("first_name") or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.programs.insert_one(dict(new_doc))
    new_doc.pop("_id", None)
    logger.info(f"Program imported by {tgid} via code {norm}")
    return {"template": new_doc, "already_imported": False, "own": False}


# ---- Планы (назначенный экземпляр программы = снимок шаблона) ----
def _round_2_5(x):
    """Округление веса до ближайших 2.5 кг."""
    return round(round(float(x) / 2.5) * 2.5, 2)


def _remap_week_days(weeks, training_days):
    """Ремаппит тренировочные (не-rest) дни снимка плана на выбранные дни недели.

    day_index = 1..7 (Пн..Вс). Берёт непустые дни каждой недели по их текущему
    порядку и расставляет на выбранные дни. Гарантирует уникальность day_index в
    неделе (без коллизий): если тренировок больше, чем выбрано дней, лишние
    занимают ближайшие свободные дни недели. Дни отдыха не хранятся
    (отсутствующий день недели = отдых)."""
    td = sorted({int(x) for x in (training_days or []) if 1 <= int(x) <= 7})
    if not td:
        return weeks
    out = copy.deepcopy(weeks)
    # Слоты: сначала выбранные дни, затем остальные дни недели (для overflow без коллизий)
    slots = td + [x for x in range(1, 8) if x not in td]
    for w in out:
        workout_days = sorted(
            [d for d in (w.get("days") or []) if not d.get("is_rest")],
            key=lambda d: d.get("day_index", 0),
        )
        for i, d in enumerate(workout_days):
            d["day_index"] = slots[i] if i < len(slots) else (i + 1)
        workout_days.sort(key=lambda d: d.get("day_index", 0))
        w["days"] = workout_days
    return out


def _scale_and_map_weeks(weeks, tpl, maxes, training_days):
    """Масштабирует веса под максимумы спортсмена и ремаппит дни недели.
    Возвращает (weeks_copy, scaled_one_rep_max)."""
    weeks = copy.deepcopy(weeks)
    base = tpl.get("base_maxes") or {}
    default_orm = dict(tpl.get("default_one_rep_max") or {})
    scaled_orm = dict(default_orm)

    # Коэффициенты масштабирования по группам (squat/bench/deadlift)
    factors = {}
    if maxes and base:
        for g in ("squat", "bench", "deadlift"):
            try:
                if base.get(g) and maxes.get(g):
                    factors[g] = float(maxes[g]) / float(base[g])
            except (TypeError, ValueError):
                pass

    # slug -> lift_group (для масштабирования референсных 1ПМ)
    slug_lift = {}
    if factors:
        for w in weeks:
            for d in w.get("days", []):
                for e in d.get("exercises", []):
                    slug = e.get("exercise_slug")
                    lg = e.get("lift_group")
                    if slug and lg:
                        slug_lift[slug] = lg
                    f = factors.get(lg)
                    if not f:
                        continue
                    for s in e.get("sets_scheme", []) or []:
                        if s.get("weight") is not None:
                            s["weight"] = _round_2_5(float(s["weight"]) * f)
        for slug, ref in default_orm.items():
            f = factors.get(slug_lift.get(slug))
            scaled_orm[slug] = round(float(ref) * f, 1) if f else ref

    # Ремаппинг дней недели: тренировочные дни шаблона -> выбранные пользователем
    if training_days:
        weeks = _remap_week_days(weeks, training_days)

    return weeks, scaled_orm


@api_router.post("/plans", response_model=Plan)
async def create_plan(payload: PlanCreate, current: dict = Depends(get_current_user)):
    # Авторизация: план можно создавать себе (self-coached) или своему подопечному
    caller = current.get("telegram_id")
    if caller != payload.athlete_telegram_id and not await _is_coach_of(caller, payload.athlete_telegram_id):
        raise HTTPException(status_code=403, detail="Создавать план можно только себе или своему подопечному")

    weeks = payload.weeks
    name = payload.name
    source_template_id = payload.template_id
    one_rep_max = payload.one_rep_max or {}
    maxes = payload.maxes or {}
    training_days = payload.training_days or []

    if payload.template_id:
        tpl = await db.programs.find_one({"id": payload.template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        weeks = tpl["weeks"]  # снимок структуры
        if not name:
            name = tpl["name"]
        if not one_rep_max:
            one_rep_max = tpl.get("default_one_rep_max") or {}
        # Масштабирование весов под максимумы спортсмена + ремаппинг дней недели
        if maxes or training_days:
            weeks, scaled_orm = _scale_and_map_weeks(weeks, tpl, maxes, training_days)
            if maxes:
                one_rep_max = scaled_orm

    if weeks is None:
        raise HTTPException(status_code=400, detail="Either template_id or weeks must be provided")

    # Один активный план: прежние активные планы спортсмена помечаем завершёнными
    # (перенесено ниже — зависит от вычисленного статуса: черновик не замещает план)

    # Видимость: тренер, готовящий план другому спортсмену → по умолчанию черновик
    coach_id = payload.coach_telegram_id
    is_coach_prepared = bool(coach_id and coach_id != payload.athlete_telegram_id)
    if payload.visibility in ("draft", "published"):
        visibility = payload.visibility
    else:
        visibility = "draft" if is_coach_prepared else "published"
    prepared_by_coach = payload.prepared_by_coach or is_coach_prepared
    now_iso = datetime.now(timezone.utc).isoformat()

    # Статус: опубликованный план становится единственным «живым» планом спортсмена;
    # черновик тренера НЕ замещает и НЕ гасит текущий рабочий план спортсмена (B2).
    status = "active" if visibility == "published" else "draft"
    if status == "active":
        await db.plans.update_many(
            {"athlete_telegram_id": payload.athlete_telegram_id,
             "status": {"$in": ["active", "draft"]}},
            {"$set": {"status": "completed", "updated_at": now_iso}},
        )

    plan = Plan(
        athlete_telegram_id=payload.athlete_telegram_id,
        coach_telegram_id=payload.coach_telegram_id,
        source_template_id=source_template_id,
        name=name or "Мой план",
        status=status,
        start_date=payload.start_date,
        weeks=weeks,
        one_rep_max=one_rep_max,
        maxes=maxes,
        training_days=sorted(set(int(d) for d in training_days)) if training_days else [],
        visibility=visibility,
        published_at=now_iso if visibility == "published" else None,
        prepared_by_coach=prepared_by_coach,
    )
    doc = plan.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.plans.insert_one(doc)
    logger.info(f"Plan created: {plan.id} for athlete={plan.athlete_telegram_id} (visibility={visibility})")
    return plan


@api_router.get("/plans/active/{telegram_id}", response_model=Optional[Plan])
async def get_active_plan(telegram_id: int):
    doc = await db.plans.find_one(
        {"athlete_telegram_id": telegram_id, "status": "active"},
        {"_id": 0},
    )
    if not doc:
        # Активного плана нет, но тренер мог готовить черновик «заранее» —
        # показываем спортсмену «план готовится» без содержимого (B2).
        draft = await db.plans.find_one(
            {"athlete_telegram_id": telegram_id, "status": "draft"},
            {"_id": 0}, sort=[("updated_at", -1)],
        )
        if draft:
            draft["weeks"] = []
            return draft
        return None
    # Черновик тренера: спортсмену не показываем содержимое («план готовится»)
    if doc.get("visibility") == "draft":
        doc["weeks"] = []
        return doc
    # Опубликованный план: скрываем содержимое ещё не открытых недель (B3),
    # сохраняя сами недели (с флагом published) для корректной навигации.
    for w in doc.get("weeks", []) or []:
        if w.get("published") is False:
            w["days"] = []
    return doc  # может быть None → вернётся null


@api_router.get("/plans/{plan_id}", response_model=Plan)
async def get_plan(plan_id: str):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")
    return doc


# ===========================================================================
# P3 — Приглашения тренера, связь тренер↔спортсмен, подопечные
# ===========================================================================
@api_router.post("/coach/invite")
async def coach_invite(payload: CoachInviteReq):
    """Тренер получает (или генерирует) invite-код + deep link для приглашения спортсмена."""
    user = await db.users.find_one({"telegram_id": payload.coach_telegram_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    roles = set(user.get("roles") or ["athlete"])
    roles.update(["athlete", "coach"])
    set_fields = {"roles": sorted(roles), "updated_at": datetime.now(timezone.utc).isoformat()}
    code = user.get("invite_code")
    if not code:
        code = await _unique_invite_code()
        set_fields["invite_code"] = code
    await db.users.update_one({"telegram_id": payload.coach_telegram_id}, {"$set": set_fields})

    bot = await _get_bot_username()
    deep_link = f"https://t.me/{bot}?startapp=coach_{code}" if bot else None
    return {"invite_code": code, "deep_link": deep_link, "bot_username": bot}


@api_router.post("/coach/link")
async def coach_link(payload: CoachLinkReq):
    """Спортсмен привязывается к тренеру по коду (инициатива спортсмена = согласие → active)."""
    code = (payload.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Код не указан")
    coach = await db.users.find_one({"invite_code": code}, {"_id": 0})
    if not coach:
        raise HTTPException(status_code=404, detail="Тренер с таким кодом не найден")
    coach_tgid = coach["telegram_id"]
    if coach_tgid == payload.athlete_telegram_id:
        raise HTTPException(status_code=400, detail="Нельзя привязать самого себя")

    athlete = await db.users.find_one({"telegram_id": payload.athlete_telegram_id}, {"_id": 0})
    if not athlete:
        raise HTTPException(status_code=404, detail="Спортсмен не найден")

    now = datetime.now(timezone.utc).isoformat()
    existing = await db.coach_links.find_one(
        {"coach_telegram_id": coach_tgid, "athlete_telegram_id": payload.athlete_telegram_id},
        {"_id": 0},
    )
    if existing:
        await db.coach_links.update_one(
            {"coach_telegram_id": coach_tgid, "athlete_telegram_id": payload.athlete_telegram_id},
            {"$set": {"status": "active", "updated_at": now}},
        )
    else:
        link = CoachLink(coach_telegram_id=coach_tgid, athlete_telegram_id=payload.athlete_telegram_id)
        doc = link.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        doc["updated_at"] = doc["updated_at"].isoformat()
        await db.coach_links.insert_one(doc)

    # У спортсмена один активный тренер: ревокируем прочие активные связи (B1)
    await db.coach_links.update_many(
        {"athlete_telegram_id": payload.athlete_telegram_id,
         "coach_telegram_id": {"$ne": coach_tgid}, "status": "active"},
        {"$set": {"status": "revoked", "updated_at": now}},
    )
    await db.users.update_one(
        {"telegram_id": payload.athlete_telegram_id},
        {"$set": {"coach_telegram_id": coach_tgid, "updated_at": now}},
    )
    logger.info(f"Coach link: coach={coach_tgid} <- athlete={payload.athlete_telegram_id}")
    return {"status": "active", "coach": _user_brief(coach)}


@api_router.post("/coach/unlink")
async def coach_unlink(payload: CoachUnlinkReq):
    """Спортсмен отвязывается от текущего тренера."""
    athlete = await db.users.find_one({"telegram_id": payload.athlete_telegram_id}, {"_id": 0})
    if not athlete:
        raise HTTPException(status_code=404, detail="Спортсмен не найден")
    coach_tgid = athlete.get("coach_telegram_id")
    now = datetime.now(timezone.utc).isoformat()
    if coach_tgid:
        await db.coach_links.update_one(
            {"coach_telegram_id": coach_tgid, "athlete_telegram_id": payload.athlete_telegram_id},
            {"$set": {"status": "revoked", "updated_at": now}},
        )
    await db.users.update_one(
        {"telegram_id": payload.athlete_telegram_id},
        {"$set": {"coach_telegram_id": None, "updated_at": now}},
    )
    return {"ok": True}


@api_router.get("/athlete/{telegram_id}/coach")
async def athlete_coach(telegram_id: int):
    """Текущий тренер спортсмена (или null)."""
    athlete = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    if not athlete:
        raise HTTPException(status_code=404, detail="User not found")
    coach_tgid = athlete.get("coach_telegram_id")
    if not coach_tgid:
        return {"coach": None}
    coach = await db.users.find_one({"telegram_id": coach_tgid}, {"_id": 0})
    return {"coach": _user_brief(coach)}


@api_router.get("/coach/{telegram_id}/clients")
async def coach_clients(telegram_id: int):
    """Список подопечных тренера + краткая активность (активный план, последняя/текущая сессия)."""
    links = await db.coach_links.find(
        {"coach_telegram_id": telegram_id, "status": "active"}, {"_id": 0}
    ).to_list(500)
    clients = []
    for link in links:
        a_id = link["athlete_telegram_id"]
        user = await db.users.find_one({"telegram_id": a_id}, {"_id": 0})
        # План, которым управляет тренер: приоритет черновику (готовится), иначе активный (B2)
        plan = await db.plans.find_one(
            {"athlete_telegram_id": a_id, "status": "draft"}, {"_id": 0},
            sort=[("updated_at", -1)],
        ) or await db.plans.find_one(
            {"athlete_telegram_id": a_id, "status": "active"}, {"_id": 0},
        )
        active_session = await db.workout_sessions.find_one(
            {"athlete_telegram_id": a_id, "status": "in_progress"}, {"_id": 0}
        )
        last_session = await db.workout_sessions.find_one(
            {"athlete_telegram_id": a_id, "status": "finished"},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        clients.append({
            "athlete": _user_brief(user),
            "plan": ({
                "id": plan["id"], "name": plan.get("name"),
                "visibility": plan.get("visibility", "published"),
                "current_week": plan.get("current_week", 1),
                "weeks_count": len(plan.get("weeks", [])),
                "prepared_by_coach": plan.get("prepared_by_coach", False),
            } if plan else None),
            "is_training_now": bool(active_session),
            "active_session_id": active_session["id"] if active_session else None,
            "last_workout_at": last_session.get("finished_at") if last_session else None,
            "linked_at": link.get("created_at"),
        })
    return {"coach_telegram_id": telegram_id, "clients": clients}


async def _assert_coach_of(coach_tgid: int, athlete_tgid: int):
    link = await db.coach_links.find_one(
        {"coach_telegram_id": coach_tgid, "athlete_telegram_id": athlete_tgid, "status": "active"},
        {"_id": 0},
    )
    if not link:
        raise HTTPException(status_code=403, detail="Вы не тренер этого спортсмена")


async def _is_coach_of(coach_tgid: int, athlete_tgid: int) -> bool:
    link = await db.coach_links.find_one(
        {"coach_telegram_id": coach_tgid, "athlete_telegram_id": athlete_tgid, "status": "active"},
        {"_id": 0},
    )
    return bool(link)


async def _assert_can_read_stats(current: dict, athlete_tgid: int):
    """Статистику видит только сам спортсмен или его активный тренер."""
    tgid = current.get("telegram_id")
    if tgid == athlete_tgid:
        return
    if await _is_coach_of(tgid, athlete_tgid):
        return
    raise HTTPException(status_code=403, detail="Нет доступа к этой статистике")


async def _assert_can_edit_plan(current: dict, plan: dict):
    """Право на изменение плана: владелец-спортсмен ИЛИ активный тренер спортсмена
    (привязанный или указанный в plan.coach_telegram_id). Иначе 403."""
    tgid = current.get("telegram_id")
    athlete = plan.get("athlete_telegram_id")
    if tgid == athlete:
        return
    if plan.get("coach_telegram_id") == tgid and await _is_coach_of(tgid, athlete):
        return
    if await _is_coach_of(tgid, athlete):
        return
    raise HTTPException(status_code=403, detail="Недостаточно прав для изменения этого плана")


async def _assert_session_read(current: dict, session: dict):
    """Просмотр тренировки: владелец-спортсмен ИЛИ активный тренер спортсмена."""
    tgid = current.get("telegram_id")
    athlete = session.get("athlete_telegram_id")
    if tgid == athlete:
        return
    if await _is_coach_of(tgid, athlete):
        return
    raise HTTPException(status_code=403, detail="Нет доступа к этой тренировке")


async def _assert_session_actor(current: dict, session: dict, actor: str, by: Optional[int]):
    """Изменение тренировки: владелец-спортсмен ИЛИ активный тренер спортсмена.
    Для actor=='coach' дополнительно проверяем, что вызывающий и есть этот тренер."""
    tgid = current.get("telegram_id")
    athlete = session.get("athlete_telegram_id")
    if actor == "coach":
        coach_id = by if by is not None else tgid
        if tgid != coach_id:
            raise HTTPException(status_code=403, detail="Действие от имени другого тренера запрещено")
        await _assert_coach_of(coach_id, athlete)
        return
    if tgid == athlete:
        return
    if await _is_coach_of(tgid, athlete):
        return
    raise HTTPException(status_code=403, detail="Нет доступа к этой тренировке")


async def _resolve_athlete_coach(athlete_tgid: int) -> Optional[int]:
    """Текущий активный тренер спортсмена (по coach_links). None, если нет."""
    link = await db.coach_links.find_one(
        {"athlete_telegram_id": athlete_tgid, "status": "active"},
        {"_id": 0, "coach_telegram_id": 1},
        sort=[("updated_at", -1)],
    )
    return link.get("coach_telegram_id") if link else None


@api_router.get("/coach/{telegram_id}/clients/{athlete_id}/plan", response_model=Optional[Plan])
async def coach_client_plan(telegram_id: int, athlete_id: int):
    """План подопечного, которым управляет тренер (полный, в т.ч. черновик).
    Приоритет — черновик (готовится тренером), иначе активный план (B2)."""
    await _assert_coach_of(telegram_id, athlete_id)
    doc = await db.plans.find_one(
        {"athlete_telegram_id": athlete_id, "status": "draft"}, {"_id": 0},
        sort=[("updated_at", -1)],
    ) or await db.plans.find_one(
        {"athlete_telegram_id": athlete_id, "status": "active"}, {"_id": 0},
    )
    return doc


@api_router.get("/coach/{telegram_id}/clients/{athlete_id}/session")
async def coach_client_session(telegram_id: int, athlete_id: int):
    """Живая (или последняя) тренировка подопочного для экрана наблюдения тренера.

    Возвращает текущую активную (in_progress) сессию, либо последнюю сессию за
    сегодня. Если активной/сегодняшней сессии нет — `null` (тренировка не идёт).
    Coach-gated: 403, если тренер не привязан к спортсмену.
    """
    await _assert_coach_of(telegram_id, athlete_id)
    s = await db.workout_sessions.find_one(
        {"athlete_telegram_id": athlete_id, "status": "in_progress"},
        {"_id": 0}, sort=[("created_at", -1)],
    )
    if not s:
        today = datetime.now(timezone.utc).date().isoformat()
        s = await db.workout_sessions.find_one(
            {"athlete_telegram_id": athlete_id, "date": today},
            {"_id": 0}, sort=[("created_at", -1)],
        )
    if not s:
        return None
    return _serialize_session(s)


# ===========================================================================
# P3 — Видимость плана, публикация недель, тренировочные дни
# ===========================================================================
async def _get_plan_or_404(plan_id: str) -> dict:
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")
    return doc


@api_router.patch("/plans/{plan_id}/visibility", response_model=Plan)
async def set_plan_visibility(plan_id: str, payload: VisibilityReq,
                             current: dict = Depends(get_current_user)):
    vis = (payload.visibility or "").strip().lower()
    if vis not in ("draft", "published"):
        raise HTTPException(status_code=400, detail="visibility должен быть draft или published")
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"visibility": vis, "updated_at": now}
    if vis == "published":
        # Публикация делает план единственным «живым»: промоутим в active и
        # завершаем прочие планы спортсмена (старый рабочий план уступает место).
        set_fields["status"] = "active"
        if not plan.get("published_at"):
            set_fields["published_at"] = now
        await db.plans.update_many(
            {"athlete_telegram_id": plan.get("athlete_telegram_id"),
             "status": {"$in": ["active", "draft"]}, "id": {"$ne": plan_id}},
            {"$set": {"status": "completed", "updated_at": now}},
        )
    await db.plans.update_one({"id": plan_id}, {"$set": set_fields})
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "plan.published", {"visibility": vis})
    await _notify_user(updated.get("athlete_telegram_id"), "plan.published",
                       {"plan_id": plan_id, "visibility": vis})
    return updated


@api_router.patch("/plans/{plan_id}/weeks/{week}/publish", response_model=Plan)
async def publish_plan_week(plan_id: str, week: int, payload: WeekPublishReq,
                            current: dict = Depends(get_current_user)):
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    weeks = plan.get("weeks", [])
    found = False
    for w in weeks:
        if w.get("week_index") == week:
            w["published"] = bool(payload.published)
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Week not found")
    await db.plans.update_one(
        {"id": plan_id},
        {"$set": {"weeks": weeks, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "week.published", {"week_index": week, "published": bool(payload.published)})
    await _notify_user(updated.get("athlete_telegram_id"), "week.published",
                       {"plan_id": plan_id, "week_index": week, "published": bool(payload.published)})
    return updated


@api_router.patch("/plans/{plan_id}/training-days", response_model=Plan)
async def set_plan_training_days(plan_id: str, payload: TrainingDaysReq,
                                 current: dict = Depends(get_current_user)):
    days = payload.training_days or []
    if any((not isinstance(d, int)) or d < 1 or d > 7 for d in days):
        raise HTTPException(status_code=400, detail="training_days: числа 1..7")
    norm = sorted(set(int(d) for d in days))
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    set_fields = {"training_days": norm, "updated_at": datetime.now(timezone.utc).isoformat()}
    # Ремаппим дни снимка плана, чтобы спортсмен реально увидел изменение в календаре.
    # Без этого недельный селектор/прогресс берут дни из week.days и не реагируют на training_days.
    if norm:
        set_fields["weeks"] = _remap_week_days(plan.get("weeks") or [], norm)
    await db.plans.update_one({"id": plan_id}, {"$set": set_fields})
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "training_days.updated", {"training_days": norm})
    await _notify_user(updated.get("athlete_telegram_id"), "training_days.updated",
                       {"plan_id": plan_id, "training_days": norm})
    return updated


# ===========================================================================
# P4 (pre) — Редактор плана подопечного: недели / дни / упражнения
# Тренер (или владелец) правит снимок плана. %1ПМ/тоннаж считаются при чтении.
# ===========================================================================
class PlanMetaReq(BaseModel):
    name: Optional[str] = None
    current_week: Optional[int] = None
    start_date: Optional[str] = None


class PlanDayUpsertReq(BaseModel):
    week: int
    day: int
    title: Optional[str] = None
    is_rest: Optional[bool] = None


class PlanExerciseReq(BaseModel):
    week: int
    day: int
    order: Optional[int] = None           # задан → редактируем; иначе добавляем
    exercise_name: str
    exercise_slug: Optional[str] = None
    exercise_id: Optional[str] = None
    muscle_group: Optional[str] = None
    difficulty: Optional[str] = None
    lift_group: Optional[str] = None
    is_accessory: bool = False
    weight_type: str = "kg"
    target_reps: Optional[str] = None
    target_rpe: Optional[float] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    sets_scheme: Optional[List[dict]] = None


def _norm_sets_scheme(scheme):
    out = []
    for s in scheme or []:
        try:
            w = s.get("weight")
            w = float(w) if w not in (None, "") else None
        except Exception:
            w = None
        try:
            sets = int(s.get("sets") or 1)
        except Exception:
            sets = 1
        try:
            reps = int(s.get("reps") or 0)
        except Exception:
            reps = 0
        out.append({"weight": w, "sets": max(1, sets), "reps": max(0, reps)})
    return out


def _normalize_plan_exercise(payload: "PlanExerciseReq", order: int) -> dict:
    scheme = _norm_sets_scheme(payload.sets_scheme)
    if scheme:
        target_sets = sum(s["sets"] for s in scheme)
        target_reps = payload.target_reps or str(scheme[0]["reps"])
        target_weight = scheme[0]["weight"]
    else:
        target_sets = 4 if payload.is_accessory else 3
        target_reps = payload.target_reps or "10"
        target_weight = None
    return {
        "exercise_id": payload.exercise_id,
        "exercise_slug": payload.exercise_slug,
        "exercise_name": (payload.exercise_name or "").strip() or "Упражнение",
        "muscle_group": payload.muscle_group,
        "difficulty": payload.difficulty,
        "order": order,
        "target_sets": target_sets,
        "target_reps": str(target_reps),
        "target_weight": target_weight,
        "weight_type": payload.weight_type or "kg",
        "target_rpe": payload.target_rpe,
        "rest_seconds": payload.rest_seconds,
        "notes": (payload.notes or None),
        "sets_scheme": scheme,
        "lift_group": payload.lift_group,
        "is_accessory": bool(payload.is_accessory),
    }


def _find_week(plan: dict, week: int):
    return next((w for w in plan.get("weeks", []) if w.get("week_index") == week), None)


def _find_day(week_obj: dict, day: int):
    return next((d for d in (week_obj.get("days") or []) if d.get("day_index") == day), None)


async def _save_plan_weeks(plan_id: str, weeks: list):
    await db.plans.update_one(
        {"id": plan_id},
        {"$set": {"weeks": weeks, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    updated = await _get_plan_or_404(plan_id)
    # Real-time: правки структуры плана доходят до спортсмена «вживую» (B5)
    await _rt_plan(plan_id, "plan.updated", {})
    await _notify_user(updated.get("athlete_telegram_id"), "plan.updated", {"plan_id": plan_id})
    return updated


@api_router.patch("/plans/{plan_id}", response_model=Plan)
async def update_plan_meta(plan_id: str, payload: PlanMetaReq,
                           current: dict = Depends(get_current_user)):
    """Переименовать план / задать текущую неделю / дату старта."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    set_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.name is not None and payload.name.strip():
        set_fields["name"] = payload.name.strip()
    if payload.current_week is not None:
        set_fields["current_week"] = max(1, int(payload.current_week))
    if payload.start_date is not None:
        set_fields["start_date"] = payload.start_date
    await db.plans.update_one({"id": plan_id}, {"$set": set_fields})
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "plan.updated", {})
    await _notify_user(updated.get("athlete_telegram_id"), "plan.updated", {"plan_id": plan_id})
    return updated


@api_router.put("/plans/{plan_id}/day", response_model=Plan)
async def upsert_plan_day(plan_id: str, payload: PlanDayUpsertReq,
                          current: dict = Depends(get_current_user)):
    """Создать/изменить день недели (день = слот дня недели 1..7)."""
    if payload.day < 1 or payload.day > 7:
        raise HTTPException(status_code=400, detail="day: 1..7")
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    week_obj = _find_week(plan, payload.week)
    if not week_obj:
        raise HTTPException(status_code=404, detail="Week not found")
    day_obj = _find_day(week_obj, payload.day)
    if day_obj:
        if payload.title is not None:
            day_obj["title"] = payload.title
        if payload.is_rest is not None:
            day_obj["is_rest"] = bool(payload.is_rest)
    else:
        week_obj.setdefault("days", []).append({
            "day_index": payload.day,
            "title": payload.title or f"День {payload.day}",
            "is_rest": bool(payload.is_rest) if payload.is_rest is not None else False,
            "exercises": [],
        })
        week_obj["days"].sort(key=lambda d: d.get("day_index", 0))
    return await _save_plan_weeks(plan_id, plan["weeks"])


@api_router.delete("/plans/{plan_id}/day", response_model=Plan)
async def delete_plan_day(plan_id: str, week: int, day: int,
                          current: dict = Depends(get_current_user)):
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    week_obj = _find_week(plan, week)
    if not week_obj:
        raise HTTPException(status_code=404, detail="Week not found")
    days = week_obj.get("days") or []
    new_days = [d for d in days if d.get("day_index") != day]
    if len(new_days) == len(days):
        raise HTTPException(status_code=404, detail="Day not found")
    week_obj["days"] = new_days
    return await _save_plan_weeks(plan_id, plan["weeks"])


@api_router.put("/plans/{plan_id}/exercise", response_model=Plan)
async def upsert_plan_exercise(plan_id: str, payload: PlanExerciseReq,
                               current: dict = Depends(get_current_user)):
    """Добавить (order=None) или изменить (order задан) упражнение в дне."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    week_obj = _find_week(plan, payload.week)
    if not week_obj:
        raise HTTPException(status_code=404, detail="Week not found")
    day_obj = _find_day(week_obj, payload.day)
    if not day_obj:
        raise HTTPException(status_code=404, detail="Day not found (создайте день сначала)")
    exs = sorted(day_obj.get("exercises") or [], key=lambda x: x.get("order", 0))
    if payload.order is not None and 0 <= int(payload.order) < len(exs):
        exs[int(payload.order)] = _normalize_plan_exercise(payload, int(payload.order))
    else:
        exs.append(_normalize_plan_exercise(payload, len(exs)))
    for i, e in enumerate(exs):
        e["order"] = i
    day_obj["exercises"] = exs
    return await _save_plan_weeks(plan_id, plan["weeks"])


@api_router.delete("/plans/{plan_id}/exercise", response_model=Plan)
async def delete_plan_exercise(plan_id: str, week: int, day: int, order: int,
                               current: dict = Depends(get_current_user)):
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    week_obj = _find_week(plan, week)
    if not week_obj:
        raise HTTPException(status_code=404, detail="Week not found")
    day_obj = _find_day(week_obj, day)
    if not day_obj:
        raise HTTPException(status_code=404, detail="Day not found")
    exs = sorted(day_obj.get("exercises") or [], key=lambda x: x.get("order", 0))
    if order < 0 or order >= len(exs):
        raise HTTPException(status_code=404, detail="Exercise not found")
    del exs[order]
    for i, e in enumerate(exs):
        e["order"] = i
    day_obj["exercises"] = exs
    return await _save_plan_weeks(plan_id, plan["weeks"])


@api_router.post("/plans/{plan_id}/week", response_model=Plan)
async def add_plan_week(plan_id: str, current: dict = Depends(get_current_user)):
    """Добавить пустую неделю в конец плана."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    weeks = plan.get("weeks") or []
    next_index = (max((w.get("week_index", 0) for w in weeks), default=0)) + 1
    weeks.append({"week_index": next_index, "published": True, "days": []})
    return await _save_plan_weeks(plan_id, weeks)


@api_router.delete("/plans/{plan_id}/week", response_model=Plan)
async def delete_plan_week(plan_id: str, week: int,
                           current: dict = Depends(get_current_user)):
    """Удалить неделю и пере-нумеровать оставшиеся (1..N)."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    weeks = sorted(plan.get("weeks") or [], key=lambda w: w.get("week_index", 0))
    new_weeks = [w for w in weeks if w.get("week_index") != week]
    if len(new_weeks) == len(weeks):
        raise HTTPException(status_code=404, detail="Week not found")
    for i, w in enumerate(new_weeks):
        w["week_index"] = i + 1
    now = datetime.now(timezone.utc).isoformat()
    cur = plan.get("current_week", 1)
    new_cur = min(max(1, cur), len(new_weeks)) if new_weeks else 1
    await db.plans.update_one(
        {"id": plan_id},
        {"$set": {"weeks": new_weeks, "current_week": new_cur, "updated_at": now}},
    )
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "plan.updated", {})
    await _notify_user(updated.get("athlete_telegram_id"), "plan.updated", {"plan_id": plan_id})
    return updated




# ===========================================================================
# Хелперы Фазы 2 (расчёт %1ПМ, схемы подходов, статистика сессии)
# ===========================================================================
_DIFF_RANK = {"Легко": 1, "Средне": 2, "Тяжело": 3}


def _int_or_zero(v):
    if isinstance(v, int):
        return v
    if v is None:
        return 0
    m = re.match(r"\s*(\d+)", str(v))
    return int(m.group(1)) if m else 0


def _resolve_sets(pe, orm):
    """Список рабочих подходов с рассчитанным %1ПМ. pe — ProgramExercise dict."""
    slug = pe.get("exercise_slug")
    scheme = pe.get("sets_scheme") or []
    if not scheme:
        scheme = [{
            "weight": pe.get("target_weight"),
            "sets": pe.get("target_sets") or 1,
            "reps": _int_or_zero(pe.get("target_reps")),
        }]
    out = []
    for s in scheme:
        w = s.get("weight")
        out.append({
            "weight": w,
            "sets": s.get("sets") or 1,
            "reps": s.get("reps") or 0,
            "percent_1rm": percent_of(w, slug, orm),
        })
    return out


def _expand_set_logs(sets_scheme):
    """Разворачивает групповую схему (weight×sets×reps) в плоский чек-лист
    индивидуальных подходов для по-подходного логирования."""
    logs = []
    for grp in (sets_scheme or []):
        n = max(1, int(grp.get("sets") or 1))
        for _ in range(n):
            logs.append({
                "weight": grp.get("weight"),
                "reps": int(grp.get("reps") or 0),
                "percent_1rm": grp.get("percent_1rm"),
                "done": False,
                "skipped": False,
            })
    return logs


def _scheme_from_logs(set_logs, only_done=True):
    """Собирает групповую схему (weight×sets×reps) из плоского списка подходов.
    Подряд идущие одинаковые (вес, повторы, %) сворачиваются в одну группу.
    only_done=True — учитывать только выполненные подходы (факт)."""
    groups = []
    for lg in (set_logs or []):
        if only_done and not lg.get("done"):
            continue
        w = lg.get("weight")
        r = int(lg.get("reps") or 0)
        p = lg.get("percent_1rm")
        if groups and groups[-1]["weight"] == w and groups[-1]["reps"] == r and groups[-1].get("percent_1rm") == p:
            groups[-1]["sets"] += 1
        else:
            groups.append({"weight": w, "sets": 1, "reps": r, "percent_1rm": p})
    return groups


def _view_exercise(pe, orm, order, status="pending"):
    """Унифицированная карточка упражнения для экрана дня/сессии."""
    is_acc = bool(pe.get("is_accessory"))
    sets = [] if is_acc else _resolve_sets(pe, orm)
    return {
        "order": order,
        "exercise_id": pe.get("exercise_id"),
        "exercise_slug": pe.get("exercise_slug"),
        "exercise_name": pe.get("exercise_name"),
        "muscle_group": pe.get("muscle_group"),
        "muscle_letter": muscle_letter(pe.get("muscle_group")),
        "difficulty": pe.get("difficulty"),
        "sets_scheme": sets,
        "plan_sets_scheme": [dict(s) for s in sets],
        "set_logs": [],
        "rest_seconds": pe.get("rest_seconds"),
        "tonnage": scheme_tonnage(sets),
        "status": status,
        "comment": pe.get("comment"),
        "edited": pe.get("edited", False),
        "lift_group": pe.get("lift_group"),
        "is_accessory": is_acc,
        "filled_by": None,
    }


def _day_group_difficulty(exercises):
    group = group_letters([e.get("muscle_group") for e in exercises])
    diffs = [e.get("difficulty") for e in exercises if e.get("difficulty")]
    difficulty = max(diffs, key=lambda d: _DIFF_RANK.get(d, 0)) if diffs else None
    return group, difficulty


def _build_session_exercises(day_obj, orm):
    ordered = sorted(day_obj.get("exercises", []), key=lambda x: x.get("order", 0))
    exs = [_view_exercise(pe, orm, i) for i, pe in enumerate(ordered)]
    for ex in exs:
        # По-подходный чек-лист строим только для основных упражнений (у подсобных
        # нет схемы подходов — они отмечаются целиком).
        if not ex.get("is_accessory"):
            ex["set_logs"] = _expand_set_logs(ex.get("sets_scheme"))
    if exs:
        exs[0]["status"] = "in_progress"
    return exs


def _est_1rm(weight, percent_1rm, reps):
    """Оценка 1ПМ по фактическому исполнению (формула Эпли): вес × (1 + повт/30).
    Если повторы неизвестны — fallback: вес ÷ (плановый % / 100)."""
    if not weight:
        return None
    try:
        r = int(reps or 0)
        if r == 1:
            return round(float(weight), 1)
        if r > 1:
            return round(float(weight) * (1 + r / 30.0), 1)
        if percent_1rm:
            return round(float(weight) / (float(percent_1rm) / 100.0), 1)
        return round(float(weight), 1)
    except Exception:
        return None


def _sets_count(scheme):
    """Суммарное число рабочих подходов в схеме (Σ sets)."""
    return sum(int(s.get("sets") or 0) for s in (scheme or []))


def _top_set(scheme):
    """Подход с максимальным весом в схеме (или None)."""
    best = None
    for s in (scheme or []):
        w = s.get("weight")
        if w is None:
            continue
        if best is None or w > best.get("weight", -1):
            best = s
    return best


def _lift_summary(exs):
    """Сводка по основным движениям (squat/bench/deadlift) из выполненных
    упражнений: топовый рабочий вес и оценка 1ПМ «по плану» (вес ÷ план%)."""
    lifts = {}
    for e in exs:
        lg = e.get("lift_group")
        if lg not in ("squat", "bench", "deadlift"):
            continue
        if e.get("status") != "done":
            continue
        fact_top = _top_set(e.get("sets_scheme"))
        if not fact_top:
            continue
        plan_top = _top_set(e.get("plan_sets_scheme")) or fact_top
        w = fact_top.get("weight")
        # 1ПМ «как в таблице»: фактический вес ÷ плановый % (фикс. интенсивность плана)
        pct = (plan_top or {}).get("percent_1rm") or fact_top.get("percent_1rm")
        one_rm = _est_1rm(w, pct, fact_top.get("reps"))
        cur = lifts.get(lg)
        if not cur or (w or 0) > (cur.get("top_weight") or 0):
            lifts[lg] = {
                "top_weight": w,
                "reps": fact_top.get("reps"),
                "percent_1rm": pct,
                "one_rm": one_rm,
            }
    return lifts


def _muscle_sets(exs):
    """Распределение выполненных подходов по буквам мышечных групп: {letter: sets}."""
    dist = {}
    for e in exs:
        if e.get("status") != "done":
            continue
        ltr = e.get("muscle_letter") or muscle_letter(e.get("muscle_group"))
        if not ltr:
            continue
        n = _sets_count(e.get("sets_scheme")) or 1
        dist[ltr] = dist.get(ltr, 0) + n
    return dist


def _session_stats(session):
    exs = session.get("exercises", [])
    total = len(exs)
    done = [e for e in exs if e.get("status") == "done"]
    skipped = [e for e in exs if e.get("status") == "skipped"]
    tonnage = round(sum(e.get("tonnage", 0) or 0 for e in done))
    group = group_letters([e.get("muscle_group") for e in exs])
    diffs = [e.get("difficulty") for e in exs if e.get("difficulty")]
    difficulty = max(diffs, key=lambda d: _DIFF_RANK.get(d, 0)) if diffs else None

    started = session.get("started_at")
    finished = session.get("finished_at")
    duration_sec = 0
    if started:
        try:
            start_dt = datetime.fromisoformat(started) if isinstance(started, str) else started
            if finished:
                end_dt = datetime.fromisoformat(finished) if isinstance(finished, str) else finished
            else:
                end_dt = datetime.now(timezone.utc)
            duration_sec = max(0, int((end_dt - start_dt).total_seconds()))
        except Exception:
            duration_sec = 0

    progress_pct = round(len(done) / total * 100) if total else 0

    # --- P7: объём (подходы) план vs факт, тоннаж план vs факт ---
    sets_done = sum(_sets_count(e.get("sets_scheme")) for e in done)
    sets_planned = sum(_sets_count(e.get("plan_sets_scheme") or e.get("sets_scheme")) for e in exs)
    tonnage_planned = round(sum(scheme_tonnage(e.get("plan_sets_scheme") or e.get("sets_scheme")) for e in exs))
    volume_pct = round(sets_done / sets_planned * 100) if sets_planned else 0
    tonnage_dev_pct = round((tonnage - tonnage_planned) / tonnage_planned * 100) if tonnage_planned else 0

    return {
        "tonnage": tonnage,
        "tonnage_planned": tonnage_planned,
        "tonnage_dev_pct": tonnage_dev_pct,
        "group": group,
        "difficulty": difficulty,
        "duration_sec": duration_sec,
        "done_count": len(done),
        "skipped_count": len(skipped),
        "total_count": total,
        "progress_pct": progress_pct,
        "sets_done": sets_done,
        "sets_planned": sets_planned,
        "volume_pct": volume_pct,
        "muscle_sets": _muscle_sets(exs),
        "lifts": _lift_summary(exs),
    }


def _deviation_flags(plan_scheme, fact_scheme, status):
    """Флаги отклонения упражнения: список строк."""
    flags = []
    if status == "skipped":
        return ["skipped"]
    p_sets = _sets_count(plan_scheme)
    f_sets = _sets_count(fact_scheme)
    if f_sets > p_sets:
        flags.append("more_volume")
    elif f_sets < p_sets and p_sets:
        flags.append("less_volume")
    p_top = _top_set(plan_scheme)
    f_top = _top_set(fact_scheme)
    pw = p_top.get("weight") if p_top else None
    fw = f_top.get("weight") if f_top else None
    if pw is not None and fw is not None:
        if fw > pw:
            flags.append("weight_up")
        elif fw < pw:
            flags.append("weight_down")
    return flags


def _session_deviation(session):
    """План vs факт по упражнениям одной сессии (для отчёта об отклонениях)."""
    items = []
    for e in session.get("exercises", []):
        plan_scheme = e.get("plan_sets_scheme") or []
        fact_scheme = e.get("sets_scheme") or []
        items.append({
            "order": e.get("order"),
            "exercise_name": e.get("exercise_name"),
            "lift_group": e.get("lift_group"),
            "muscle_group": e.get("muscle_group"),
            "status": e.get("status"),
            "edited": bool(e.get("edited")),
            "planned": {
                "sets": _sets_count(plan_scheme),
                "tonnage": scheme_tonnage(plan_scheme),
                "scheme": plan_scheme,
            },
            "actual": {
                "sets": _sets_count(fact_scheme) if e.get("status") == "done" else 0,
                "tonnage": e.get("tonnage", 0) if e.get("status") == "done" else 0,
                "scheme": fact_scheme,
            },
            "flags": _deviation_flags(plan_scheme, fact_scheme, e.get("status")),
        })
    return items


def _serialize_session(session):
    out = dict(session)
    out.pop("_id", None)
    out["stats"] = _session_stats(session)
    return out


# ===========================================================================
# P4 — Real-time helpers (persist-then-broadcast)
# ===========================================================================
async def _can_access_plan(tgid: int, plan_id: str) -> bool:
    """Имеет ли пользователь доступ к комнате плана: владелец-спортсмен,
    привязанный тренер или указанный coach_telegram_id плана."""
    plan = await db.plans.find_one(
        {"id": plan_id},
        {"_id": 0, "athlete_telegram_id": 1, "coach_telegram_id": 1},
    )
    if not plan:
        return False
    athlete = plan.get("athlete_telegram_id")
    if athlete == tgid or plan.get("coach_telegram_id") == tgid:
        return True
    link = await db.coach_links.find_one(
        {"coach_telegram_id": tgid, "athlete_telegram_id": athlete, "status": "active"},
        {"_id": 0},
    )
    return bool(link)


async def _rt_session(plan_id: Optional[str], event_type: str, session: dict):
    """Broadcast события сессии в комнату плана. Payload содержит готовый
    снимок сессии — клиент применяет его без дополнительного REST-запроса."""
    if not plan_id:
        return
    try:
        await manager.broadcast(
            f"plan:{plan_id}",
            event_type,
            {"session_id": session.get("id"), "plan_id": plan_id, "session": _serialize_session(session)},
        )
    except Exception as e:
        logger.warning(f"rt_session broadcast failed: {e}")


async def _rt_plan(plan_id: Optional[str], event_type: str, extra: Optional[dict] = None):
    """Broadcast события плана (видимость/недели/дни) в комнату плана."""
    if not plan_id:
        return
    try:
        payload = {"plan_id": plan_id}
        if extra:
            payload.update(extra)
        await manager.broadcast(f"plan:{plan_id}", event_type, payload)
    except Exception as e:
        logger.warning(f"rt_plan broadcast failed: {e}")


async def _notify_user(telegram_id: Optional[int], event_type: str, payload: dict):
    """Личное уведомление пользователю (комната user:{telegram_id})."""
    if telegram_id is None:
        return
    try:
        await manager.broadcast(f"user:{telegram_id}", event_type, payload)
    except Exception as e:
        logger.warning(f"notify_user broadcast failed: {e}")


async def _touch_session_event(session_id: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id}, {"$set": {"last_event_at": ts}}
    )
    return ts


# ---- День плана (превью перед стартом) ----
@api_router.get("/plans/{plan_id}/day")
async def get_plan_day(plan_id: str, week: int = 1, day: int = 1,
                       viewer: Optional[int] = None):
    """День плана: упражнения + мета. day = 1..7 (Пн..Вс).

    viewer — telegram_id смотрящего. Если смотрит сам спортсмен (владелец), а
    неделя ещё не опубликована тренером (`published=false`) — содержимое скрыто
    (locked), чтобы работала выдача недель «по одной» (B3)."""
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    orm = doc.get("one_rep_max") or {}
    rest_response = {
        "plan_id": plan_id, "week_index": week, "day_index": day,
        "is_rest": True, "title": "День отдыха", "exercises": [],
        "group": "", "difficulty": None,
    }
    week_obj = next((w for w in (doc.get("weeks") or []) if w.get("week_index") == week), None)
    if not week_obj:
        return rest_response
    # Неделя скрыта от самого спортсмена — отдаём «заблокировано»
    is_owner = viewer is not None and viewer == doc.get("athlete_telegram_id")
    if is_owner and week_obj.get("published") is False:
        return {**rest_response, "is_rest": True, "locked": True,
                "title": "Неделя ещё не открыта тренером"}
    day_obj = next((d for d in (week_obj.get("days") or []) if d.get("day_index") == day), None)
    if not day_obj or day_obj.get("is_rest"):
        return rest_response

    ordered = sorted(day_obj.get("exercises", []), key=lambda x: x.get("order", 0))
    exercises = [_view_exercise(pe, orm, i) for i, pe in enumerate(ordered)]
    group, difficulty = _day_group_difficulty(exercises)
    return {
        "plan_id": plan_id, "week_index": week, "day_index": day_obj["day_index"],
        "title": day_obj.get("title", ""), "is_rest": False,
        "group": group, "difficulty": difficulty,
        "exercises": exercises,
    }


@api_router.get("/plans/{plan_id}/week-progress")
async def get_week_progress(plan_id: str, week: int = 1, viewer: Optional[int] = None,
                            dates: Optional[str] = None):
    """Прогресс/расписание по дням недели (для колец в селекторе).

    viewer — telegram_id смотрящего; для владельца скрытая неделя возвращается
    как заблокированная (7 дней отдыха + locked) — выдача недель «по одной» (B3).

    dates — опц. список из 7 ISO-дат (через запятую) для day_index 1..7 текущей
    КАЛЕНДАРНОЙ недели. Если задан, прогресс дня берётся из сессии, реально
    выполненной В ЭТУ дату (session.date), а не просто по (week,day). Это
    исключает «протекание» прогресса на одинаковые дни недели соседних недель."""
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    week_obj = next((w for w in (doc.get("weeks") or []) if w.get("week_index") == week), None)
    is_owner = viewer is not None and viewer == doc.get("athlete_telegram_id")
    locked = bool(week_obj and is_owner and week_obj.get("published") is False)
    days_map = {}
    if week_obj and not locked:
        for d in (week_obj.get("days") or []):
            if d.get("is_rest"):
                continue
            planned_sets = sum(int(e.get("target_sets", 0) or 0) for e in d.get("exercises", []))
            days_map[d.get("day_index")] = {
                "title": d.get("title", ""),
                "exercise_count": len(d.get("exercises", [])),
                "planned_sets": planned_sets,
            }

    # Календарные даты дней недели (day_index 1..7), если переданы
    date_by_day = {}
    if dates:
        parts = [p.strip() for p in dates.split(",")]
        for i, iso in enumerate(parts[:7]):
            if iso:
                date_by_day[i + 1] = iso

    # Сессии этой недели — для реального прогресса колец
    sessions = await db.workout_sessions.find(
        {"plan_id": plan_id, "week_index": week}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    sess_by_day = {}
    for s in sessions:
        di = s.get("day_index")
        if date_by_day:
            # привязка к реальной дате выполнения
            if s.get("date") and s.get("date") == date_by_day.get(di):
                sess_by_day[di] = s
        else:
            sess_by_day[di] = s

    days = []
    for di in range(1, 8):
        info = days_map.get(di)
        s = sess_by_day.get(di)
        if info:
            progress_pct = 0
            is_done = False
            if s:
                st = _session_stats(s)
                progress_pct = st["progress_pct"]
                is_done = s.get("status") == "finished"
            days.append({
                "day_index": di, "is_workout": True, "title": info["title"],
                "exercise_count": info["exercise_count"], "planned_sets": info["planned_sets"],
                "progress_pct": progress_pct, "is_done": is_done, "has_session": bool(s),
            })
        else:
            days.append({
                "day_index": di, "is_workout": False, "title": "Отдых",
                "exercise_count": 0, "planned_sets": 0,
                "progress_pct": 0, "is_done": False, "has_session": False,
            })
    return {"plan_id": plan_id, "week_index": week, "days": days, "locked": locked}


# ===========================================================================
# Тренировочные сессии (Phase 2)
# ===========================================================================
@api_router.post("/sessions/start")
async def start_session(req: SessionStartReq, current_user: dict = Depends(get_current_user)):
    plan = await db.plans.find_one({"id": req.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Старт «под диктовку тренера»: проверяем, что вызывающий — тренер этого спортсмена
    coach_led = req.coach_telegram_id is not None
    uid = current_user["telegram_id"]
    if coach_led:
        if uid != req.coach_telegram_id:
            raise HTTPException(status_code=403, detail="Старт от имени другого тренера запрещён")
        await _assert_coach_of(req.coach_telegram_id, req.athlete_telegram_id)
    else:
        # Обычный старт: только сам спортсмен или его активный тренер
        if uid != req.athlete_telegram_id and not await _is_coach_of(uid, req.athlete_telegram_id):
            raise HTTPException(status_code=403, detail="Нельзя начать тренировку за другого спортсмена")

    existing = await db.workout_sessions.find_one(
        {"plan_id": req.plan_id, "athlete_telegram_id": req.athlete_telegram_id,
         "week_index": req.week, "day_index": req.day, "status": {"$ne": "finished"},
         **({"date": req.date} if req.date else {})},
        {"_id": 0},
    )
    if existing:
        return _serialize_session(existing)

    # Запрет нескольких одновременных тренировок: незавершённая сессия в другой день
    active_other = await db.workout_sessions.find_one(
        {"athlete_telegram_id": req.athlete_telegram_id, "status": "in_progress"},
        {"_id": 0},
    )
    if active_other:
        raise HTTPException(status_code=409, detail={
            "error": "active_session_exists",
            "message": ("У спортсмена уже есть активная тренировка. Завершите её, чтобы начать новую."
                        if coach_led else
                        "У вас уже есть активная тренировка. Завершите её, чтобы начать новую."),
            "session_id": active_other["id"],
            "plan_id": active_other.get("plan_id"),
            "week_index": active_other.get("week_index"),
            "day_index": active_other.get("day_index"),
        })

    week_obj = next((w for w in (plan.get("weeks") or []) if w.get("week_index") == req.week), None)
    # Нельзя начать тренировку в скрытой (неопубликованной) тренером неделе —
    # но тренер, ведущий тренировку «под диктовку», может стартовать любую неделю.
    if (week_obj and week_obj.get("published") is False
            and plan.get("athlete_telegram_id") == req.athlete_telegram_id
            and not coach_led):
        raise HTTPException(status_code=400, detail="Эта неделя ещё не открыта тренером")
    day_obj = next((d for d in (week_obj.get("days") or []) if d.get("day_index") == req.day), None) if week_obj else None
    if not day_obj or day_obj.get("is_rest"):
        raise HTTPException(status_code=400, detail="No workout scheduled for this day")

    # Тренер сессии: из плана, иначе инициатор старта, иначе из активной связи спортсмена
    coach_for_session = (plan.get("coach_telegram_id")
                         or req.coach_telegram_id
                         or await _resolve_athlete_coach(req.athlete_telegram_id))

    orm = plan.get("one_rep_max") or {}
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": str(uuid.uuid4()),
        "plan_id": req.plan_id,
        "athlete_telegram_id": req.athlete_telegram_id,
        "coach_telegram_id": coach_for_session,
        "week_index": req.week, "day_index": req.day,
        "date": req.date or datetime.now(timezone.utc).date().isoformat(),
        "title": day_obj.get("title", ""),
        "status": "in_progress", "paused": False,
        "started_by": "coach" if coach_led else "athlete",
        "started_at": now, "finished_at": None,
        "exercises": _build_session_exercises(day_obj, orm),
        "last_event_at": now,
        "created_at": now, "updated_at": now,
    }
    await db.workout_sessions.insert_one(dict(session))
    logger.info(f"Session started ({session['started_by']}): {session['id']} plan={req.plan_id} day={req.day}")
    # Real-time: оповестить комнату плана и лично тренера
    await _rt_session(req.plan_id, "session.started", session)
    await _notify_user(coach_for_session, "session.started", {
        "session_id": session["id"], "plan_id": req.plan_id,
        "athlete_telegram_id": req.athlete_telegram_id,
        "week_index": req.week, "day_index": req.day, "title": session["title"],
    })
    return _serialize_session(session)


@api_router.get("/sessions/active")
async def get_active_session(plan_id: str, week: int, day: int, athlete: int,
                             date: Optional[str] = None,
                             current_user: dict = Depends(get_current_user)):
    """Сессия для дня плана. Если передан date (ISO YYYY-MM-DD) — возвращаем
    сессию, реально выполненную В ЭТУ календарную дату (иначе последнюю по
    (plan,week,day)). Это исключает показ одной тренировки на одинаковых днях
    недели разных календарных недель."""
    # Доступ: только сам спортсмен или его активный тренер
    if current_user["telegram_id"] != athlete and not await _is_coach_of(current_user["telegram_id"], athlete):
        raise HTTPException(status_code=403, detail="Нет доступа к тренировкам этого спортсмена")
    q = {"plan_id": plan_id, "athlete_telegram_id": athlete,
         "week_index": week, "day_index": day}
    if date:
        q["date"] = date
    s = await db.workout_sessions.find_one(
        q, {"_id": 0}, sort=[("created_at", -1)],
    )
    if not s:
        return None
    return _serialize_session(s)


@api_router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    await _assert_session_read(current_user, s)
    return _serialize_session(s)


@api_router.patch("/sessions/{session_id}/exercise/{order}")
async def update_session_exercise(
    session_id: str,
    order: int,
    action: str,
    actor: str = "athlete",
    by: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """Отметка упражнения (done/skip/reset).

    actor: "athlete" (по умолчанию) или "coach" — кто отмечает. Если actor=="coach",
    проверяем, что `by` (telegram_id тренера) действительно тренер этого спортсмена.
    Заполняется поле `filled_by` для real-time co-scribe.
    """
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if actor == "coach" and by is None:
        raise HTTPException(status_code=400, detail="Не указан тренер (by)")
    await _assert_session_actor(current_user, s, actor, by)

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")

    if action == "done":
        # «Выполнить всё» = все подходы сделаны как в плане (с учётом ранее
        # внесённого факта по отдельным подходам).
        for lg in target.get("set_logs") or []:
            lg["done"] = True
            lg["skipped"] = False
        if target.get("set_logs"):
            target["sets_scheme"] = _scheme_from_logs(target["set_logs"], only_done=True)
            target["tonnage"] = scheme_tonnage(target["sets_scheme"])
        target["status"] = "done"
        target["filled_by"] = actor
    elif action == "skip":
        # «Пропустить всё» = все подходы помечаются пропущенными
        for lg in target.get("set_logs") or []:
            lg["skipped"] = True
            lg["done"] = False
        if target.get("set_logs"):
            target["sets_scheme"] = _scheme_from_logs(target["set_logs"], only_done=True)
            target["tonnage"] = scheme_tonnage(target["sets_scheme"])
        target["status"] = "skipped"
        target["filled_by"] = actor
    elif action == "reset":
        for lg in target.get("set_logs") or []:
            lg["done"] = False
            lg["skipped"] = False
        if target.get("set_logs"):
            # Возвращаем плановую схему как ориентир (упражнение снова pending)
            target["sets_scheme"] = [dict(s) for s in (target.get("plan_sets_scheme") or [])]
            target["tonnage"] = scheme_tonnage(target["sets_scheme"])
        target["status"] = "pending"
        target["filled_by"] = None
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Следующее ожидающее упражнение делаем активным, если активного не осталось
    if not any(e["status"] == "in_progress" for e in exs):
        nxt = next((e for e in exs if e["status"] == "pending"), None)
        if nxt:
            nxt["status"] = "in_progress"

    now = datetime.now(timezone.utc).isoformat()
    status = s.get("status", "in_progress")
    finished_at = s.get("finished_at")
    just_finished = False
    if exs and all(e["status"] in ("done", "skipped") for e in exs):
        if status != "finished":
            just_finished = True
        status = "finished"
        finished_at = finished_at or now

    set_fields = {"exercises": exs, "status": status, "finished_at": finished_at,
                  "updated_at": now, "last_event_at": now}
    # P7: при завершении замораживаем снимок статистики тренировки
    if status == "finished":
        s["exercises"] = exs
        s["finished_at"] = finished_at
        set_fields["stats"] = _session_stats(s)
    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": set_fields},
    )
    s["exercises"] = exs
    s["status"] = status
    s["finished_at"] = finished_at
    s["last_event_at"] = now
    # Real-time broadcast: либо обновление, либо завершение
    await _rt_session(s.get("plan_id"), "session.finished" if just_finished else "session.updated", s)
    if just_finished:
        await _notify_user(s.get("coach_telegram_id"), "session.finished", {
            "session_id": s["id"], "plan_id": s.get("plan_id"),
            "athlete_telegram_id": s["athlete_telegram_id"],
        })
    return _serialize_session(s)


class SetLogReq(BaseModel):
    done: Optional[bool] = None
    skipped: Optional[bool] = None
    weight: Optional[float] = None
    reps: Optional[int] = None


@api_router.patch("/sessions/{session_id}/exercise/{order}/set/{set_index}")
async def log_session_set(
    session_id: str,
    order: int,
    set_index: int,
    payload: SetLogReq = Body(default=None),
    actor: str = "athlete",
    by: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """По-подходное логирование факта: отметка подхода выполненным/пропущенным
    и/или запись фактических веса/повторов конкретного подхода.

    actor: "athlete" (по умолчанию) | "coach". Тренер (actor=="coach", by=telegram_id)
    может заполнять подходы подопечного в реальном времени (co-scribe).
    """
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if actor == "coach" and by is None:
        raise HTTPException(status_code=400, detail="Не указан тренер (by)")
    await _assert_session_actor(current_user, s, actor, by)

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")
    logs = target.get("set_logs") or []
    if set_index < 0 or set_index >= len(logs):
        raise HTTPException(status_code=404, detail="Set not found")

    payload = payload or SetLogReq()
    lg = logs[set_index]
    changed = False
    if payload.weight is not None and payload.weight != lg.get("weight"):
        lg["weight"] = payload.weight
        changed = True
    if payload.reps is not None and int(payload.reps) != int(lg.get("reps") or 0):
        lg["reps"] = max(0, int(payload.reps))
        changed = True
    # Пропуск и выполнение — взаимоисключающие состояния подхода
    if payload.skipped is not None:
        lg["skipped"] = bool(payload.skipped)
        if lg["skipped"]:
            lg["done"] = False
    if payload.done is not None:
        lg["done"] = bool(payload.done)
        if lg["done"]:
            lg["skipped"] = False
    target["set_logs"] = logs
    if changed:
        target["edited"] = True

    # Факт. схема и тоннаж — из выполненных подходов
    target["sets_scheme"] = _scheme_from_logs(logs, only_done=True)
    target["tonnage"] = scheme_tonnage(target["sets_scheme"])

    # Статус упражнения по чек-листу: подход «улажен», если выполнен или пропущен
    settled = [bool(x.get("done") or x.get("skipped")) for x in logs]
    all_settled = len(logs) > 0 and all(settled)
    any_settled = any(settled)
    any_done = any(x.get("done") for x in logs)
    if all_settled:
        if target.get("status") not in ("done", "skipped"):
            target["filled_by"] = actor
        target["status"] = "done" if any_done else "skipped"
    else:
        target["status"] = "in_progress" if any_settled else (target.get("status") or "pending")

    # Активное упражнение: следующий pending → in_progress, если активного нет
    if not any(e["status"] == "in_progress" for e in exs):
        nxt = next((e for e in exs if e["status"] == "pending"), None)
        if nxt:
            nxt["status"] = "in_progress"

    now = datetime.now(timezone.utc).isoformat()
    status = s.get("status", "in_progress")
    finished_at = s.get("finished_at")
    just_finished = False
    all_closed = bool(exs) and all(e["status"] in ("done", "skipped") for e in exs)
    if all_closed:
        if status != "finished":
            just_finished = True
        status = "finished"
        finished_at = finished_at or now
    elif status == "finished":
        # Тренировка была завершена, но появились незакрытые упражнения — снова активна
        status = "in_progress"
        finished_at = None

    set_fields = {"exercises": exs, "status": status, "finished_at": finished_at,
                  "updated_at": now, "last_event_at": now}
    if status == "finished":
        s["exercises"] = exs
        s["finished_at"] = finished_at
        set_fields["stats"] = _session_stats(s)
    await db.workout_sessions.update_one({"id": session_id}, {"$set": set_fields})
    s["exercises"] = exs
    s["status"] = status
    s["finished_at"] = finished_at
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.finished" if just_finished else "session.updated", s)
    if just_finished:
        await _notify_user(s.get("coach_telegram_id"), "session.finished", {
            "session_id": s["id"], "plan_id": s.get("plan_id"),
            "athlete_telegram_id": s["athlete_telegram_id"],
        })
    return _serialize_session(s)


@api_router.patch("/sessions/{session_id}/exercise/{order}/edit")
async def edit_session_exercise(
    session_id: str,
    order: int,
    payload: dict = Body(...),
    actor: str = "athlete",
    by: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """Редактирование упражнения сессии (кнопка ✨): имя и/или схема подходов.

    actor: "athlete" | "coach". Тренер (actor=="coach", by=telegram_id тренера)
    может править упражнение подопечного в реальном времени (co-scribe)."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if actor == "coach" and by is None:
        raise HTTPException(status_code=400, detail="Не указан тренер (by)")
    await _assert_session_actor(current_user, s, actor, by)
    plan = await db.plans.find_one({"id": s["plan_id"]}, {"_id": 0})
    orm = (plan or {}).get("one_rep_max") or {}

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")

    changed = False
    if payload.get("exercise_name"):
        if payload["exercise_name"] != target.get("exercise_name"):
            changed = True
        target["exercise_name"] = payload["exercise_name"]
    if isinstance(payload.get("sets_scheme"), list):
        slug = target.get("exercise_slug")
        old_norm = [
            (float(s.get("weight")) if s.get("weight") is not None else None,
             int(s.get("sets") or 0), int(s.get("reps") or 0))
            for s in (target.get("sets_scheme") or [])
        ]
        new_sets = []
        for st in payload["sets_scheme"]:
            w = st.get("weight")
            new_sets.append({
                "weight": w,
                "sets": max(1, int(st.get("sets") or 1)),
                "reps": max(0, int(st.get("reps") or 0)),
                "percent_1rm": percent_of(w, slug, orm),
            })
        new_norm = [
            (float(s["weight"]) if s["weight"] is not None else None, s["sets"], s["reps"])
            for s in new_sets
        ]
        if new_norm != old_norm:
            changed = True
        target["sets_scheme"] = new_sets
        target["tonnage"] = scheme_tonnage(new_sets)
        # Пересобираем по-подходный чек-лист под новую схему, сохраняя отметки
        # выполнения по позициям. Для уже завершённого упражнения держим факт.
        # схему в согласии с логами.
        old_logs = target.get("set_logs") or []
        if old_logs:
            new_logs = _expand_set_logs(new_sets)
            for i, nl in enumerate(new_logs):
                if i < len(old_logs):
                    if old_logs[i].get("done"):
                        nl["done"] = True
                    if old_logs[i].get("skipped"):
                        nl["skipped"] = True
            target["set_logs"] = new_logs
            if target.get("status") == "done":
                target["sets_scheme"] = _scheme_from_logs(new_logs, only_done=True)
                target["tonnage"] = scheme_tonnage(target["sets_scheme"])
    # Комментарий спортсмена тренеру (виден тренеру). Пустая строка/None -> сброс.
    if "comment" in payload:
        c = payload.get("comment")
        if c is None:
            target["comment"] = None
        else:
            c = str(c).strip()
            target["comment"] = c[:500] if c else None
    # Флажок "изменено" ставим только при реальной правке названия/подходов
    if changed:
        target["edited"] = True

    now = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id}, {"$set": {"exercises": exs, "updated_at": now, "last_event_at": now}}
    )
    s["exercises"] = exs
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.updated", s)
    return _serialize_session(s)


@api_router.post("/sessions/{session_id}/finish")
async def finish_session(session_id: str, current_user: dict = Depends(get_current_user)):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    await _assert_session_actor(current_user, s, "athlete", None)
    now = datetime.now(timezone.utc).isoformat()
    finished_at = s.get("finished_at") or now
    s["status"] = "finished"
    s["finished_at"] = finished_at
    frozen = _session_stats(s)
    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "finished", "finished_at": finished_at, "updated_at": now,
                  "last_event_at": now, "stats": frozen}},
    )
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.finished", s)
    await _notify_user(s.get("coach_telegram_id"), "session.finished", {
        "session_id": s["id"], "plan_id": s.get("plan_id"),
        "athlete_telegram_id": s["athlete_telegram_id"],
    })
    return _serialize_session(s)


@api_router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Продолжить ранее завершённую тренировку, СОХРАНИВ отметки о выполненных
    упражнениях. Сессия снова становится активной (in_progress); следующее
    невыполненное упражнение делается текущим. Запрещаем, если у спортсмена уже
    есть ДРУГАЯ активная тренировка (409)."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    await _assert_session_actor(current_user, s, "athlete", None)

    active_other = await db.workout_sessions.find_one(
        {"athlete_telegram_id": s["athlete_telegram_id"], "status": "in_progress",
         "id": {"$ne": session_id}},
        {"_id": 0},
    )
    if active_other:
        raise HTTPException(status_code=409, detail={
            "error": "active_session_exists",
            "message": "У вас уже есть активная тренировка. Завершите её, чтобы продолжить эту.",
            "session_id": active_other["id"],
            "plan_id": active_other.get("plan_id"),
            "week_index": active_other.get("week_index"),
            "day_index": active_other.get("day_index"),
        })

    now = datetime.now(timezone.utc).isoformat()
    exs = s.get("exercises") or []
    # Сохраняем все отметки (done/skipped/filled_by). Просто
    # реактивируем следующее невыполненное упражнение, если активного нет.
    if not any(e.get("status") == "in_progress" for e in exs):
        nxt = next((e for e in exs if e.get("status") == "pending"), None)
        if nxt:
            nxt["status"] = "in_progress"

    set_fields = {
        "exercises": exs,
        "status": "in_progress",
        "paused": False,
        "finished_at": None,
        "last_event_at": now,
        "updated_at": now,
    }
    await db.workout_sessions.update_one({"id": session_id}, {"$set": set_fields})
    s2 = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    logger.info(f"Session resumed: {session_id}")
    await _rt_session(s2.get("plan_id"), "session.updated", s2)
    await _notify_user(s2.get("coach_telegram_id"), "session.updated", {
        "session_id": s2["id"], "plan_id": s2.get("plan_id"),
        "athlete_telegram_id": s2["athlete_telegram_id"],
    })
    return _serialize_session(s2)


@api_router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str, resume: bool = False, current_user: dict = Depends(get_current_user)):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    await _assert_session_actor(current_user, s, "athlete", None)
    now = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id}, {"$set": {"paused": (not resume), "updated_at": now, "last_event_at": now}}
    )
    s["paused"] = (not resume)
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.updated", s)
    return _serialize_session(s)


# ---- Сводная статистика спортсмена (серия/streak) ----
@api_router.get("/stats/{telegram_id}")
async def get_athlete_stats(telegram_id: int, current: dict = Depends(get_current_user)):
    await _assert_can_read_stats(current, telegram_id)
    sessions = await db.workout_sessions.find(
        {"athlete_telegram_id": telegram_id, "status": "finished"},
        {"_id": 0, "finished_at": 1, "date": 1, "exercises": 1},
    ).to_list(2000)
    # Засчитываем тренировку только если реально выполнено хотя бы одно упражнение
    valid = [s for s in sessions
             if any(e.get("status") == "done" for e in (s.get("exercises") or []))]
    streak, active_days = _calendar_streak(valid)
    return {"telegram_id": telegram_id, "streak_days": streak,
            "total_workouts": len(valid), "active_days": active_days}


# ===========================================================================
# P7 — Хелперы агрегированной статистики и пропусков
# ===========================================================================
from seed import LETTER_ORDER as _LETTER_ORDER  # порядок букв групп мышц

_LETTER_NAMES = {
    "Н": "Ноги", "Г": "Грудь", "С": "Спина", "П": "Плечи", "Р": "Руки", "К": "Кор",
}
_LIFT_NAMES = {"squat": "Присед", "bench": "Жим", "deadlift": "Становая"}


def _parse_date(s):
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s).date()
        return date.fromisoformat(s[:10])
    except Exception:
        try:
            return date.fromisoformat(str(s)[:10])
        except Exception:
            return None


def _session_day(s):
    """Единый календарный день сессии: date (день по плану) → finished_at."""
    return _parse_date(s.get("date")) or _parse_date(s.get("finished_at"))


def _iso_week_key(d):
    if not d:
        return None
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _get_session_stats(s):
    """Берём замороженный снимок статистики, иначе считаем на лету."""
    st = s.get("stats")
    if st and isinstance(st, dict) and "tonnage" in st:
        return st
    return _session_stats(s)


def _plan_planned_days(plan):
    """Список запланированных (не-rest) тренировочных дней плана с числом подходов."""
    days = []
    for w in (plan.get("weeks") or []):
        wi = w.get("week_index")
        for d in (w.get("days") or []):
            if d.get("is_rest"):
                continue
            exs = d.get("exercises") or []
            if not exs:
                continue
            sets_planned = 0
            for e in exs:
                sc = e.get("sets_scheme") or []
                sets_planned += _sets_count(sc) if sc else int(e.get("target_sets") or 0)
            days.append({
                "week_index": wi,
                "day_index": d.get("day_index"),
                "title": d.get("title", ""),
                "exercise_count": len(exs),
                "sets_planned": sets_planned,
            })
    days.sort(key=lambda x: (x["week_index"] or 0, x["day_index"] or 0))
    return days


async def _collect_day_marks(plan_id):
    docs = await db.plan_day_marks.find({"plan_id": plan_id}, {"_id": 0}).to_list(2000)
    return {(d.get("week_index"), d.get("day_index")): d for d in docs}


async def _streak_mode(tg):
    u = await db.users.find_one({"telegram_id": tg}, {"_id": 0, "settings": 1})
    return ((u or {}).get("settings") or {}).get("streak_mode") or "strict"


async def _schedule_and_streak(plan, streak_mode):
    """Adherence по расписанию + тренировочный streak (с учётом пропусков/переносов).

    Дни без привязки к календарю: «достигнутые» дни — все запланированные дни
    до самого дальнего (week, day), на котором уже была сессия (фронтир)."""
    plan_id = plan["id"]
    planned = _plan_planned_days(plan)
    sess = await db.workout_sessions.find(
        {"plan_id": plan_id},
        {"_id": 0, "week_index": 1, "day_index": 1, "status": 1, "exercises": 1},
    ).to_list(3000)
    completed = set()
    frontier = None
    for s in sess:
        t = (s.get("week_index") or 1, s.get("day_index") or 1)
        if frontier is None or t > frontier:
            frontier = t
        if s.get("status") == "finished" and any(
            e.get("status") == "done" for e in (s.get("exercises") or [])
        ):
            completed.add(t)
    marks = await _collect_day_marks(plan_id)
    reached = [p for p in planned
               if frontier and (p["week_index"], p["day_index"]) <= frontier]

    counts = {"completed": 0, "missed": 0, "skipped": 0, "excused": 0, "rescheduled": 0}
    rows = []
    num = denom = 0
    for p in reached:
        k = (p["week_index"], p["day_index"])
        if k in completed:
            status = "completed"
            num += 1
            denom += 1
        elif k in marks:
            status = marks[k].get("status") or "skipped"
            if status not in ("excused", "rescheduled"):
                denom += 1
        else:
            status = "missed"
            denom += 1
        counts[status] = counts.get(status, 0) + 1
        rows.append({**p, "status": status, "mark": marks.get(k)})

    schedule_pct = round(num / denom * 100) if denom else 0

    streak = 0
    for p in reversed(reached):
        k = (p["week_index"], p["day_index"])
        if k in completed:
            streak += 1
            continue
        if k in marks:
            ms = marks[k].get("status")
            if ms in ("excused", "rescheduled"):
                continue
            if ms == "skipped" and streak_mode == "lenient" and marks[k].get("reason"):
                continue
        break

    return {
        "rows": rows, "counts": counts, "schedule_pct": schedule_pct,
        "workout_streak": streak, "planned_total": len(planned),
        "reached_total": len(reached), "marks": marks, "frontier": frontier,
    }


def _calendar_streak(sessions):
    dates = set()
    for s in sessions:
        if not any(e.get("status") == "done" for e in (s.get("exercises") or [])):
            continue
        d = _session_day(s)
        if d:
            dates.add(d)
    streak = 0
    if dates:
        today = datetime.now(timezone.utc).date()
        cur = today if today in dates else (today - timedelta(days=1))
        while cur in dates:
            streak += 1
            cur = cur - timedelta(days=1)
    return streak, len(dates)


async def _finished_sessions(tg, plan_id=None, frm=None, to=None):
    q = {"athlete_telegram_id": tg, "status": "finished"}
    if plan_id:
        q["plan_id"] = plan_id
    docs = await db.workout_sessions.find(q, {"_id": 0}).sort("finished_at", 1).to_list(3000)
    fr = _parse_date(frm) if frm else None
    tt = _parse_date(to) if to else None
    out = []
    for s in docs:
        if not any(e.get("status") == "done" for e in (s.get("exercises") or [])):
            continue
        d = _session_day(s)
        if (fr or tt) and not d:
            continue
        if fr and d < fr:
            continue
        if tt and d > tt:
            continue
        out.append(s)
    return out


async def _resolve_stats_plan(tg, plan_id):
    if plan_id:
        p = await db.plans.find_one({"id": plan_id}, {"_id": 0})
        if p:
            return p
    return await db.plans.find_one(
        {"athlete_telegram_id": tg, "status": "active"}, {"_id": 0}
    )


async def _athlete_detailed_stats(tg, frm=None, to=None, plan_id=None):
    plan = await _resolve_stats_plan(tg, plan_id)
    use_plan_week = bool(plan_id and plan)   # по микроциклам только при явном выборе плана
    sessions = await _finished_sessions(tg, plan_id if plan_id else None, frm, to)

    # Если фильтр по плану ничего не дал, но план есть — оставляем пусто (честно)
    total_tonnage = total_tonnage_planned = 0
    total_sets_done = total_sets_planned = 0
    total_duration = 0
    progress_acc = 0
    week_agg = {}
    muscle_agg = {}
    lift_best = {}  # lift_group -> {top_weight, one_rm}

    for s in sessions:
        st = _get_session_stats(s)
        total_tonnage += st.get("tonnage", 0) or 0
        total_tonnage_planned += st.get("tonnage_planned", 0) or 0
        total_sets_done += st.get("sets_done", 0) or 0
        total_sets_planned += st.get("sets_planned", 0) or 0
        total_duration += st.get("duration_sec", 0) or 0
        progress_acc += st.get("progress_pct", 0) or 0

        if use_plan_week:
            wi = s.get("week_index") or 1
            key, label, srt = wi, f"Нед {wi}", (wi,)
        else:
            d = _session_day(s)
            key = _iso_week_key(d) or "—"
            label, srt = key, (key,)
        a = week_agg.setdefault(key, {"tonnage": 0, "count": 0, "label": label, "sort": srt})
        a["tonnage"] += st.get("tonnage", 0) or 0
        a["count"] += 1

        # Считаем свежо из упражнений (а не из замороженного снимка), чтобы
        # исправленные формулы применялись и к историческим данным.
        for ltr, cnt in _muscle_sets(s.get("exercises") or []).items():
            muscle_agg[ltr] = muscle_agg.get(ltr, 0) + cnt
        for lg, info in _lift_summary(s.get("exercises") or []).items():
            cur = lift_best.get(lg)
            if not cur or (info.get("one_rm") or info.get("top_weight") or 0) > (
                cur.get("one_rm") or cur.get("top_weight") or 0
            ):
                lift_best[lg] = info

    n = len(sessions)
    week_rows = sorted(week_agg.values(), key=lambda x: x["sort"])
    tonnage_by_week = [{"week": r["label"], "tonnage": round(r["tonnage"])} for r in week_rows]
    frequency_by_week = [{"week": r["label"], "count": r["count"]} for r in week_rows]
    muscle_distribution = [
        {"group": ltr, "label": _LETTER_NAMES.get(ltr, ltr), "sets": muscle_agg[ltr]}
        for ltr in _LETTER_ORDER if ltr in muscle_agg
    ]
    for ltr in muscle_agg:  # буквы вне стандартного порядка
        if ltr not in _LETTER_ORDER:
            muscle_distribution.append(
                {"group": ltr, "label": _LETTER_NAMES.get(ltr, ltr), "sets": muscle_agg[ltr]}
            )

    # Оценка 1ПМ: план (по программе) + достигнутое (как в таблице)
    plan_maxes = (plan.get("maxes") if plan else {}) or {}
    one_rep_max_est = []
    for lift, name in _LIFT_NAMES.items():
        planned_v = plan_maxes.get(lift)
        ach = lift_best.get(lift) or {}
        achieved_v = ach.get("one_rm")
        top_v = ach.get("top_weight")
        if planned_v or achieved_v:
            one_rep_max_est.append({
                "lift": lift, "name": name,
                "planned": planned_v, "achieved": achieved_v, "top_weight": top_v,
            })

    cal_streak, _ = _calendar_streak(sessions)
    sched = None
    workout_streak = cal_streak
    if plan:
        sched = await _schedule_and_streak(plan, await _streak_mode(tg))
        workout_streak = sched["workout_streak"]

    completion_pct = min(100, round(total_sets_done / total_sets_planned * 100)) if total_sets_planned else (
        min(100, round(progress_acc / n)) if n else 0
    )
    tonnage_dev_pct = round(
        (total_tonnage - total_tonnage_planned) / total_tonnage_planned * 100
    ) if total_tonnage_planned else 0
    volume_pct = min(100, round(total_sets_done / total_sets_planned * 100)) if total_sets_planned else 0

    # Частота: по микроциклам выбранного плана или по календарным неделям
    if use_plan_week:
        avg_per_week = round(n / len(week_agg), 1) if week_agg else 0
    else:
        cal_weeks = {}
        for s in sessions:
            d = _session_day(s)
            wk = _iso_week_key(d)
            if wk:
                cal_weeks[wk] = cal_weeks.get(wk, 0) + 1
        avg_per_week = round(sum(cal_weeks.values()) / len(cal_weeks), 1) if cal_weeks else 0

    recent = []
    for s in sorted(sessions, key=lambda x: x.get("finished_at") or "", reverse=True)[:10]:
        st = _get_session_stats(s)
        recent.append({
            "id": s.get("id"), "date": s.get("date"),
            "finished_at": s.get("finished_at"),
            "title": s.get("title") or "Тренировка",
            "week_index": s.get("week_index"), "day_index": s.get("day_index"),
            "tonnage": st.get("tonnage", 0), "duration_sec": st.get("duration_sec", 0),
            "progress_pct": st.get("progress_pct", 0), "group": st.get("group", ""),
            "difficulty": st.get("difficulty"), "done_count": st.get("done_count", 0),
            "total_count": st.get("total_count", 0),
        })

    summary = {
        "total_workouts": n,
        "streak_days": cal_streak,
        "workout_streak": workout_streak,
        "avg_per_week": avg_per_week,
        "completion_pct": completion_pct,
        "total_tonnage": round(total_tonnage),
        "total_duration_sec": total_duration,
        "total_sets": total_sets_done,
    }
    adherence = {
        "volume_pct": volume_pct,
        "schedule_pct": sched["schedule_pct"] if sched else None,
        "tonnage_dev_pct": tonnage_dev_pct,
    }
    skip_counts = sched["counts"] if sched else {}

    return {
        "telegram_id": tg,
        "plan_id": plan.get("id") if plan else None,
        "plan_name": plan.get("name") if plan else None,
        "range": {"from": frm, "to": to},
        "summary": summary,
        "tonnage_by_week": tonnage_by_week,
        "frequency_by_week": frequency_by_week,
        "muscle_distribution": muscle_distribution,
        "one_rep_max_est": one_rep_max_est,
        "adherence": adherence,
        "skip_counts": skip_counts,
        "recent_sessions": recent,
    }


async def _athlete_exercise_progress(tg, slug=None, plan_id=None):
    # B4: без явного plan_id считаем «за всё время» (по всем планам, группировка по датам)
    plan = (await _resolve_stats_plan(tg, plan_id)) if plan_id else None
    by_plan = bool(plan)
    sessions = await _finished_sessions(tg, plan["id"] if plan else None)

    avail = {}
    weighted = set()
    for s in sessions:
        for e in (s.get("exercises") or []):
            sg = e.get("exercise_slug") or e.get("exercise_name")
            if not sg:
                continue
            if sg not in avail:
                avail[sg] = {
                    "slug": e.get("exercise_slug"),
                    "key": sg,
                    "name": e.get("exercise_name"),
                    "lift_group": e.get("lift_group"),
                }
            if e.get("status") == "done" and _top_set(e.get("sets_scheme")):
                weighted.add(sg)
    # B5: в выпадающем списке — только упражнения с рабочим весом
    avail = {k: v for k, v in avail.items() if k in weighted}

    target = slug
    if not target:
        for sg, info in avail.items():
            if info.get("lift_group"):
                target = sg
                break
        if not target and avail:
            target = next(iter(avail))

    series_map = {}
    for s in sessions:
        if by_plan:
            key = s.get("week_index") or 1
            label = f"Нед {key}"
            sort_key = (key,)
        else:
            d = _session_day(s)
            if not d:
                continue
            key = d.isoformat()
            label = d.strftime("%d.%m")
            sort_key = (key,)
        for e in (s.get("exercises") or []):
            if e.get("status") != "done":
                continue
            sg = e.get("exercise_slug") or e.get("exercise_name")
            if sg != target:
                continue
            fact_top = _top_set(e.get("sets_scheme"))
            if not fact_top:
                continue
            plan_top = _top_set(e.get("plan_sets_scheme")) or fact_top
            fw = fact_top.get("weight")
            pct = (plan_top or {}).get("percent_1rm") or fact_top.get("percent_1rm")
            one_rm = _est_1rm(fw, pct, fact_top.get("reps"))
            cand = {
                "label": label, "sort": sort_key,
                "week_index": s.get("week_index") if by_plan else None,
                "date": None if by_plan else key,
                "top_weight": fw, "plan_weight": (plan_top or {}).get("weight"),
                "reps": fact_top.get("reps"), "one_rm": one_rm,
                "tonnage": e.get("tonnage", 0),
            }
            row = series_map.get(key)
            if not row or (fw or 0) > (row.get("top_weight") or 0):
                series_map[key] = cand
    series = sorted(series_map.values(), key=lambda x: x["sort"])
    for r in series:
        r.pop("sort", None)
    return {
        "telegram_id": tg, "slug": target,
        "scope": "plan" if by_plan else "all",
        "name": (avail.get(target) or {}).get("name") if target else None,
        "exercises": list(avail.values()),
        "series": series,
    }


# ---- P2.1: пропуски/переносы тренировочных дней ----
async def _upsert_day_mark(plan, week, day, status, reason=None,
                           rescheduled_to=None, marked_by=None):
    plan_id = plan["id"]
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.plan_day_marks.find_one(
        {"plan_id": plan_id, "week_index": week, "day_index": day}, {"_id": 0}
    )
    if existing:
        set_fields = {"status": status, "updated_at": now}
        if reason is not None:
            set_fields["reason"] = reason
        if rescheduled_to is not None:
            set_fields["rescheduled_to"] = rescheduled_to
        if marked_by is not None:
            set_fields["marked_by"] = marked_by
        await db.plan_day_marks.update_one(
            {"plan_id": plan_id, "week_index": week, "day_index": day},
            {"$set": set_fields},
        )
        existing.update(set_fields)
        return existing
    mark = PlanDayMark(
        plan_id=plan_id, athlete_telegram_id=plan["athlete_telegram_id"],
        week_index=week, day_index=day, status=status, reason=reason,
        rescheduled_to=rescheduled_to, marked_by=marked_by,
    )
    doc = mark.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.plan_day_marks.insert_one(dict(doc))
    return doc


@api_router.post("/plans/{plan_id}/day/skip")
async def skip_plan_day(plan_id: str, payload: DaySkipReq,
                        current: dict = Depends(get_current_user)):
    """Спортсмен/тренер помечает день плана пропущенным (с причиной)."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    by = payload.marked_by or current.get("telegram_id")
    mark = await _upsert_day_mark(plan, payload.week, payload.day, "skipped",
                                  reason=payload.reason, marked_by=by)
    await _rt_plan(plan_id, "day.skipped", {
        "week_index": payload.week, "day_index": payload.day,
        "status": "skipped", "reason": payload.reason,
    })
    return mark


@api_router.post("/plans/{plan_id}/day/reschedule")
async def reschedule_plan_day(plan_id: str, payload: DayRescheduleReq,
                              current: dict = Depends(get_current_user)):
    """Перенос тренировочного дня на другую дату (не считается пропуском)."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    by = payload.marked_by or current.get("telegram_id")
    mark = await _upsert_day_mark(plan, payload.week, payload.day, "rescheduled",
                                  reason=payload.reason,
                                  rescheduled_to=payload.rescheduled_to, marked_by=by)
    await _rt_plan(plan_id, "day.rescheduled", {
        "week_index": payload.week, "day_index": payload.day,
        "rescheduled_to": payload.rescheduled_to,
    })
    return mark


@api_router.patch("/plans/{plan_id}/day/{week}/{day}/mark")
async def mark_plan_day(plan_id: str, week: int, day: int, payload: DayMarkReq,
                        current: dict = Depends(get_current_user)):
    """Тренер/владелец помечает день: excused (уважительный) / missed / skipped."""
    if payload.status not in ("excused", "missed", "skipped"):
        raise HTTPException(status_code=400, detail="status: excused | missed | skipped")
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    by = payload.marked_by or current.get("telegram_id")
    mark = await _upsert_day_mark(plan, week, day, payload.status,
                                  reason=payload.reason, marked_by=by)
    await _rt_plan(plan_id, "day.marked", {
        "week_index": week, "day_index": day, "status": payload.status,
    })
    return mark


@api_router.delete("/plans/{plan_id}/day/{week}/{day}/mark")
async def unmark_plan_day(plan_id: str, week: int, day: int,
                          current: dict = Depends(get_current_user)):
    """Снять пометку с дня (вернуть в обычное состояние)."""
    plan = await _get_plan_or_404(plan_id)
    await _assert_can_edit_plan(current, plan)
    res = await db.plan_day_marks.delete_one(
        {"plan_id": plan_id, "week_index": week, "day_index": day}
    )
    await _rt_plan(plan_id, "day.unmarked", {"week_index": week, "day_index": day})
    return {"deleted": res.deleted_count}


@api_router.get("/plans/{plan_id}/missed")
async def get_plan_missed(plan_id: str):
    """Список пропущенных/перенесённых дней + авто-определённые missed-дни."""
    plan = await _get_plan_or_404(plan_id)
    sched = await _schedule_and_streak(plan, await _streak_mode(plan["athlete_telegram_id"]))
    days = [r for r in sched["rows"] if r["status"] != "completed"]
    # Явные пометки за пределами «достигнутых» дней — тоже показываем
    reached_keys = {(r["week_index"], r["day_index"]) for r in sched["rows"]}
    for (w, d), m in (sched["marks"] or {}).items():
        if (w, d) not in reached_keys:
            days.append({
                "week_index": w, "day_index": d, "title": "",
                "status": m.get("status"), "mark": m,
            })
    days.sort(key=lambda x: (x["week_index"] or 0, x["day_index"] or 0))
    return {
        "plan_id": plan_id, "days": days, "counts": sched["counts"],
        "schedule_pct": sched["schedule_pct"], "workout_streak": sched["workout_streak"],
        "planned_total": sched["planned_total"], "reached_total": sched["reached_total"],
    }


# ---- P7: отклонения сессии и подробная статистика ----
@api_router.get("/sessions/{session_id}/deviation")
async def get_session_deviation(session_id: str, current_user: dict = Depends(get_current_user)):
    """План vs факт по упражнениям одной тренировки."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    await _assert_session_read(current_user, s)
    return {
        "session_id": session_id,
        "stats": _get_session_stats(s),
        "exercises": _session_deviation(s),
    }


@api_router.get("/stats/{telegram_id}/detailed")
async def stats_detailed(telegram_id: int, from_: Optional[str] = Query(default=None, alias="from"),
                         to: Optional[str] = None, plan_id: Optional[str] = None,
                         current: dict = Depends(get_current_user)):
    await _assert_can_read_stats(current, telegram_id)
    return await _athlete_detailed_stats(telegram_id, from_, to, plan_id)


@api_router.get("/stats/{telegram_id}/exercise-progress")
async def stats_exercise_progress(telegram_id: int, slug: Optional[str] = None,
                                  plan_id: Optional[str] = None,
                                  current: dict = Depends(get_current_user)):
    await _assert_can_read_stats(current, telegram_id)
    return await _athlete_exercise_progress(telegram_id, slug, plan_id)


# ---- P7: данные для экрана тренировочной серии (streak) ----
async def _athlete_streak_data(tg, weeks=12):
    sessions = await db.workout_sessions.find(
        {"athlete_telegram_id": tg, "status": "finished"},
        {"_id": 0, "finished_at": 1, "date": 1, "exercises": 1},
    ).to_list(3000)
    day_counts = {}
    total_sessions = 0
    for s in sessions:
        if not any(e.get("status") == "done" for e in (s.get("exercises") or [])):
            continue
        total_sessions += 1
        d = _session_day(s)
        if d:
            day_counts[d] = day_counts.get(d, 0) + 1
    dates = set(day_counts)

    today = datetime.now(timezone.utc).date()
    # текущая серия (подряд идущие дни до сегодня/вчера)
    cur = 0
    c = today if today in dates else (today - timedelta(days=1))
    while c in dates:
        cur += 1
        c -= timedelta(days=1)
    # рекорд
    best = 0
    for d in dates:
        if (d - timedelta(days=1)) not in dates:
            length = 1
            n = d + timedelta(days=1)
            while n in dates:
                length += 1
                n += timedelta(days=1)
            best = max(best, length)

    plan = await db.plans.find_one(
        {"athlete_telegram_id": tg, "status": "active"}, {"_id": 0, "training_days": 1}
    )
    weekly_goal = len((plan or {}).get("training_days") or [])

    monday = today - timedelta(days=today.weekday())
    trained_this_week = sum(1 for i in range(7) if (monday + timedelta(days=i)) in dates)

    weeks = max(1, min(int(weeks or 12), 26))
    grid = []
    cur_m = monday - timedelta(weeks=weeks - 1)
    while cur_m <= monday:
        days = []
        for i in range(7):
            dd = cur_m + timedelta(days=i)
            days.append({
                "date": dd.isoformat(),
                "weekday": i + 1,            # 1=Пн .. 7=Вс
                "trained": dd in dates,
                "count": day_counts.get(dd, 0),
                "is_today": dd == today,
                "is_future": dd > today,
            })
        grid.append({"week_start": cur_m.isoformat(), "days": days})
        cur_m += timedelta(weeks=1)

    return {
        "telegram_id": tg,
        "current_streak": cur,
        "best_streak": best,
        "total_workouts": total_sessions,
        "active_days": len(dates),
        "weekly_goal": weekly_goal,
        "trained_this_week": trained_this_week,
        "week": grid[-1] if grid else {"days": []},
        "calendar": grid,
    }


@api_router.get("/stats/{telegram_id}/streak")
async def stats_streak(telegram_id: int, weeks: int = 12,
                       current: dict = Depends(get_current_user)):
    await _assert_can_read_stats(current, telegram_id)
    return await _athlete_streak_data(telegram_id, weeks)


@api_router.get("/coach/{coach_id}/clients/{athlete_id}/stats")
async def coach_client_stats(coach_id: int, athlete_id: int,
                             from_: Optional[str] = Query(default=None, alias="from"),
                             to: Optional[str] = None, plan_id: Optional[str] = None,
                             current: dict = Depends(get_current_user)):
    if current.get("telegram_id") != coach_id:
        raise HTTPException(status_code=403, detail="Доступ от имени другого тренера запрещён")
    await _assert_coach_of(coach_id, athlete_id)
    return await _athlete_detailed_stats(athlete_id, from_, to, plan_id)


@api_router.get("/coach/{coach_id}/clients/{athlete_id}/exercise-progress")
async def coach_client_exercise_progress(coach_id: int, athlete_id: int,
                                         slug: Optional[str] = None,
                                         plan_id: Optional[str] = None,
                                         current: dict = Depends(get_current_user)):
    if current.get("telegram_id") != coach_id:
        raise HTTPException(status_code=403, detail="Доступ от имени другого тренера запрещён")
    await _assert_coach_of(coach_id, athlete_id)
    return await _athlete_exercise_progress(athlete_id, slug, plan_id)


# ===========================================================================
# P6 — ИИ-анализ программ (DeepSeek V4 Flash, OpenAI-совместимый API)
# Ключ появится позже (openmodel.ai / routerai.ru / api.deepseek.com) —
# конфигурация целиком из .env: AI_BASE_URL, AI_API_KEY, AI_MODEL.
# ===========================================================================
def _ai_config():
    return {
        "base_url": (os.environ.get("AI_BASE_URL") or "").rstrip("/"),
        "api_key": os.environ.get("AI_API_KEY") or "",
        "model": os.environ.get("AI_MODEL") or "deepseek-v4-flash",
    }


@api_router.get("/ai/status")
async def ai_status():
    cfg = _ai_config()
    return {"enabled": bool(cfg["base_url"] and cfg["api_key"]), "model": cfg["model"]}


async def _ai_chat(messages, temperature=0.3):
    cfg = _ai_config()
    if not (cfg["base_url"] and cfg["api_key"]):
        raise HTTPException(status_code=503,
                            detail="ИИ-анализ пока не настроен: не задан API-ключ сервиса")
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    body = {
        "model": cfg["model"], "messages": messages, "temperature": temperature,
        "max_tokens": 16000, "stream": False,
        "response_format": {"type": "json_object"},
    }
    url = f"{cfg['base_url']}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(url, json=body, headers=headers)
            if r.status_code == 400:
                # часть провайдеров не поддерживает response_format — повтор без него
                body.pop("response_format", None)
                r = await c.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"ИИ-сервис недоступен: {e.__class__.__name__}")
    if r.status_code >= 400:
        try:
            msg = (r.json().get("error") or {}).get("message") or r.text
        except Exception:
            msg = r.text
        raise HTTPException(status_code=502, detail=f"Ошибка ИИ-сервиса ({r.status_code}): {str(msg)[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=502, detail="Некорректный ответ ИИ-сервиса")


def _extract_json(text):
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.MULTILINE).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise HTTPException(status_code=422, detail="ИИ вернул некорректный формат — попробуйте ещё раз")
    try:
        return json.loads(s[start:end + 1])
    except Exception:
        raise HTTPException(status_code=422, detail="ИИ вернул некорректный JSON — попробуйте ещё раз")


_AI_SCHEMA = """{
 "name": "название программы (строка)",
 "description": "краткое описание (строка)",
 "level": "beginner|intermediate|advanced",
 "goal": "strength|hypertrophy|powerlifting|general",
 "weeks": [{
   "week_index": 1,
   "days": [{
     "day_index": 1,
     "title": "название дня, например 'День 1 · Присед'",
     "exercises": [{
       "name": "название упражнения (строка, по-русски)",
       "muscle_group": "legs|chest|back|shoulders|biceps|triceps|core",
       "lift_group": "squat|bench|deadlift или null",
       "is_accessory": false,
       "rest_seconds": 120,
       "sets": [{"weight": 100.0, "percent_1rm": null, "sets": 3, "reps": 5}]
     }]
   }]
 }]
}"""

_AI_SYSTEM = (
    "Ты — опытный тренер по силовым видам спорта и парсер тренировочных программ. "
    "Отвечай ТОЛЬКО валидным JSON без пояснений и markdown, строго по схеме:\n"
    + _AI_SCHEMA +
    "\nПравила:\n"
    "- week_index и day_index начинаются с 1; day_index — день недели 1..7.\n"
    "- Дни отдыха НЕ включай в структуру.\n"
    "- В 'sets' каждая запись — группа подходов: sets (кол-во подходов) × reps (повторы).\n"
    "- Если вес задан процентом от 1ПМ — заполни percent_1rm числом (например 75), а weight оставь null. "
    "percent_1rm используй только для базовых движений с lift_group (squat/bench/deadlift).\n"
    "- Если вес известен в кг — заполни weight, percent_1rm оставь null.\n"
    "- Если вес неизвестен (собственный вес, разминка) — weight и percent_1rm null.\n"
    "- is_accessory=true только для подсобки без веса (планка, гиперэкстензия без веса и т.п.).\n"
    "- lift_group: 'squat' для приседов, 'bench' для жимов лёжа, 'deadlift' для становых тяг; иначе null.\n"
    "- Названия упражнений и дней — на русском языке.\n"
    "- Выводи максимально КОМПАКТНЫЙ JSON: без лишних пробелов и переносов строк."
)

_AI_SYSTEM_GEN = _AI_SYSTEM + (
    "\n\nТы составляешь программу С НУЛЯ как элитный тренер с 15-летним опытом "
    "(пауэрлифтинг, гипертрофия, ОФП). Требования к качеству программы:\n"
    "ОБЪЁМ (самое важное):\n"
    "- Каждый тренировочный день содержит 5–8 упражнений. День из 2–4 упражнений — ГРУБАЯ ОШИБКА "
    "(допустимо только если пользователь ЯВНО попросил короткие/минимальные тренировки).\n"
    "- Структура дня: сначала 1–2 базовых многосуставных движения, затем 3–6 подсобных/изолирующих.\n"
    "- Недельный объём на каждую целевую мышечную группу: 10–20 рабочих подходов.\n"
    "ПОДБОР УПРАЖНЕНИЙ:\n"
    "- Покрывай все мышечные группы согласно цели и сплиту: ноги, грудь, спина, плечи, руки, кор.\n"
    "- Используй общепринятые русские названия: «Приседания со штангой», «Жим лёжа», «Становая тяга», "
    "«Тяга штанги в наклоне», «Подтягивания», «Жим гантелей сидя», «Румынская тяга», «Выпады с гантелями», "
    "«Тяга верхнего блока», «Французский жим», «Сгибания рук со штангой», «Разводка гантелей», "
    "«Гиперэкстензия», «Планка» и т.п.\n"
    "- Не повторяй одно упражнение дважды в один день; между днями вариативность приветствуется.\n"
    "НАГРУЗКА И ПРОГРЕССИЯ:\n"
    "- Базовые движения (lift_group) задавай через percent_1rm: сила 70–90%, гипертрофия 60–75%.\n"
    "- Прогрессия по неделям ОБЯЗАТЕЛЬНА (линейная или волновая, например 70→75→80→разгрузка 60). "
    "Недели не должны быть точными копиями друг друга.\n"
    "- Повторы по цели: сила 3–6, гипертрофия 8–15, выносливость/ОФП 12–20.\n"
    "- Подсобка/изоляция: weight и percent_1rm null (вес подберёт пользователь), 3–4 подхода по 8–15 повторов.\n"
    "- rest_seconds: базовые 150–240, подсобка 60–120.\n"
    "СПЛИТ (если пользователь не указал число дней — 3–4 дня в неделю):\n"
    "- 2–3 дня → full-body или верх/низ; 4 дня → верх/низ ×2; 5–6 дней → push/pull/legs.\n"
    "- Учитывай уровень: новичкам проще движения и меньше интенсивность, опытным — сложнее и тяжелее."
)


_AI_QUESTIONS_SYSTEM = (
    "Ты — опытный тренер по силовым видам спорта. Пользователь просит составить тренировочную программу. "
    "Перед составлением задай уточняющие вопросы. Отвечай ТОЛЬКО валидным JSON без пояснений, по схеме:\n"
    '{"questions":[{"question":"текст вопроса","options":["вариант 1","вариант 2"]}]}\n'
    "Правила:\n"
    "- Ровно 3–5 вопросов. Спрашивай ТОЛЬКО о том, чего нет в запросе пользователя (не переспрашивай известное).\n"
    "- Типичные темы: цель, уровень/опыт, дней в неделю, доступное оборудование, длительность программы (недель), "
    "известные 1ПМ в базовых движениях, травмы/ограничения, время на тренировку.\n"
    "- К каждому вопросу 3–5 коротких вариантов ответа (до 40 символов каждый), без варианта «другое».\n"
    "- Вопросы и варианты — на русском языке. Выводи компактный JSON."
)


async def _ai_build_template(data, current, source):
    """Конвертация JSON-ответа ИИ во внутренний шаблон программы + сохранение."""
    if not isinstance(data, dict) or not (data.get("weeks") or []):
        raise HTTPException(status_code=422, detail="ИИ не смог построить структуру программы")
    tgid = current.get("telegram_id")
    catalog = await db.exercises.find(
        {"$or": [{"is_builtin": True}, {"owner_telegram_id": tgid}]}, {"_id": 0}
    ).to_list(1000)
    by_name = {(ex.get("name") or "").strip().lower(): ex for ex in catalog if ex.get("name")}
    names = list(by_name.keys())

    uses_percent = False
    orm_map = {}
    weeks_out = []
    for wi, w in enumerate((data.get("weeks") or [])[:16], start=1):
        days_out = []
        used_idx = set()
        for di, d in enumerate((w.get("days") or [])[:7], start=1):
            exs_out = []
            for order, e in enumerate((d.get("exercises") or [])[:15]):
                nm = str(e.get("name") or "").strip()
                if not nm:
                    continue
                match = by_name.get(nm.lower())
                if not match:
                    close = difflib.get_close_matches(nm.lower(), names, n=1, cutoff=0.85)
                    if close:
                        match = by_name[close[0]]
                lg = e.get("lift_group")
                if lg not in ("squat", "bench", "deadlift"):
                    lg = None
                mg = e.get("muscle_group")
                if match and (match.get("muscle_groups") or []):
                    mg = match["muscle_groups"][0]

                ex_percent = False
                scheme = []
                for s in (e.get("sets") or [])[:12]:
                    try:
                        n_sets = max(1, min(20, int(s.get("sets") or 1)))
                        reps = max(0, min(100, int(s.get("reps") or 0)))
                    except (TypeError, ValueError):
                        continue
                    w_val = s.get("weight")
                    pct = s.get("percent_1rm")
                    if w_val is None and pct is not None and lg:
                        try:
                            w_val = _round_2_5(float(pct))  # base_max = 100 кг → вес ≡ проценту
                            ex_percent = True
                        except (TypeError, ValueError):
                            w_val = None
                    elif w_val is not None:
                        try:
                            w_val = round(float(w_val), 2)
                        except (TypeError, ValueError):
                            w_val = None
                    scheme.append({"weight": w_val, "sets": n_sets, "reps": reps})
                has_weight = any(s.get("weight") for s in scheme)
                is_acc = bool(e.get("is_accessory")) and not has_weight
                if ex_percent:
                    uses_percent = True
                    if match and match.get("slug"):
                        orm_map[match["slug"]] = 100.0
                try:
                    rest = int(e.get("rest_seconds")) if e.get("rest_seconds") else None
                except (TypeError, ValueError):
                    rest = None
                exs_out.append({
                    "exercise_id": (match or {}).get("id"),
                    "exercise_slug": (match or {}).get("slug"),
                    "exercise_name": (match or {}).get("name") or nm,
                    "muscle_group": mg,
                    "order": order,
                    "target_sets": sum(s["sets"] for s in scheme) or (4 if is_acc else 3),
                    "target_reps": str(scheme[0]["reps"]) if scheme else "10",
                    "weight_type": "kg",
                    "rest_seconds": rest,
                    "sets_scheme": [] if is_acc else scheme,
                    "lift_group": lg,
                    "is_accessory": is_acc,
                })
            if not exs_out:
                continue
            try:
                idx = int(d.get("day_index") or di)
            except (TypeError, ValueError):
                idx = di
            idx = min(7, max(1, idx))
            while idx in used_idx and idx < 7:
                idx += 1
            used_idx.add(idx)
            days_out.append({
                "day_index": idx,
                "title": str(d.get("title") or f"День {len(days_out) + 1}")[:60],
                "is_rest": False,
                "exercises": exs_out,
            })
        if days_out:
            days_out.sort(key=lambda x: x["day_index"])
            weeks_out.append({"week_index": wi, "published": True, "days": days_out})

    if not weeks_out:
        raise HTTPException(status_code=422, detail="ИИ не смог распознать ни одного тренировочного дня")

    level = data.get("level") if data.get("level") in ("beginner", "intermediate", "advanced") else "intermediate"
    goal = data.get("goal") if data.get("goal") in ("strength", "hypertrophy", "powerlifting", "general") else "general"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "slug": None,
        "name": str(data.get("name") or "Моя программа")[:80],
        "description": str(data.get("description") or "")[:600],
        "author": "ИИ-анализ",
        "level": level,
        "goal": goal,
        "weeks": weeks_out,
        "is_builtin": False,
        "owner_telegram_id": tgid,
        "source": source,
        "share_code": None,
        "shared_from": None,
        "tags": [],
        "default_one_rep_max": orm_map,
        "requires_maxes": uses_percent,
        "base_maxes": {"squat": 100, "bench": 100, "deadlift": 100} if uses_percent else {},
        "created_at": now,
        "updated_at": now,
    }
    _template_recount(doc)
    await db.programs.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info(f"AI template created: {doc['name']} (owner={tgid}, source={source})")
    return doc


class AiAnswer(BaseModel):
    question: str
    answer: str


class AiGenerateReq(BaseModel):
    prompt: str
    answers: list[AiAnswer] = []


class AiQuestionsReq(BaseModel):
    prompt: str


class AiParseReq(BaseModel):
    text: str


def _ai_require_enabled():
    cfg = _ai_config()
    if not (cfg["base_url"] and cfg["api_key"]):
        raise HTTPException(status_code=503,
                            detail="ИИ-анализ пока не настроен: не задан API-ключ сервиса")


async def _ai_start_job(current, kind, coro_factory):
    """Долгие ИИ-запросы (>60 c) убивает ingress — выполняем в фоне, клиент опрашивает job."""
    job_id = str(uuid.uuid4())
    await db.ai_jobs.insert_one({
        "id": job_id, "telegram_id": current.get("telegram_id"), "kind": kind,
        "status": "pending", "template": None, "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async def _run():
        try:
            tpl = await coro_factory()
            await db.ai_jobs.update_one({"id": job_id}, {"$set": {"status": "done", "template": tpl}})
        except HTTPException as e:
            await db.ai_jobs.update_one({"id": job_id}, {"$set": {"status": "error", "error": str(e.detail)}})
        except Exception:
            logger.exception(f"AI job {job_id} failed")
            await db.ai_jobs.update_one(
                {"id": job_id},
                {"$set": {"status": "error", "error": "Непредвиденная ошибка ИИ — попробуйте ещё раз"}})

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "pending"}


@api_router.get("/ai/program/jobs/{job_id}")
async def ai_job_status(job_id: str, current: dict = Depends(get_current_user)):
    job = await db.ai_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.get("telegram_id") != current.get("telegram_id"):
        raise HTTPException(status_code=403, detail="Доступ к чужой задаче запрещён")
    return job


@api_router.post("/ai/program/questions")
async def ai_program_questions(payload: AiQuestionsReq, current: dict = Depends(get_current_user)):
    """Уточняющие вопросы по первому запросу пользователя (шаг 1 генерации)."""
    prompt = (payload.prompt or "").strip()
    if len(prompt) < 10:
        raise HTTPException(status_code=400, detail="Опишите пожелания подробнее (минимум 10 символов)")
    content = await _ai_chat([
        {"role": "system", "content": _AI_QUESTIONS_SYSTEM},
        {"role": "user", "content": f"Запрос пользователя:\n{prompt[:4000]}"},
    ], temperature=0.4)
    data = _extract_json(content)
    out = []
    for q in (data.get("questions") or [])[:5]:
        qt = str(q.get("question") or "").strip()
        if not qt:
            continue
        opts = [str(o).strip()[:60] for o in (q.get("options") or [])[:6] if str(o).strip()]
        out.append({"question": qt[:200], "options": opts})
    if not out:
        raise HTTPException(status_code=422, detail="ИИ не смог составить вопросы — попробуйте ещё раз")
    return {"questions": out}


@api_router.post("/ai/program/generate")
async def ai_generate_program(payload: AiGenerateReq, current: dict = Depends(get_current_user)):
    """Генерация программы (фоновая задача): промпт + ответы на уточняющие вопросы."""
    prompt = (payload.prompt or "").strip()
    if len(prompt) < 10:
        raise HTTPException(status_code=400, detail="Опишите пожелания подробнее (минимум 10 символов)")
    _ai_require_enabled()
    extra = ""
    qa_lines = [f"- {a.question.strip()[:200]} → {a.answer.strip()[:200]}"
                for a in (payload.answers or [])[:8] if (a.answer or "").strip()]
    if qa_lines:
        extra = "\n\nОтветы пользователя на уточняющие вопросы (обязательно учти):\n" + "\n".join(qa_lines)

    async def _factory():
        content = await _ai_chat([
            {"role": "system", "content": _AI_SYSTEM_GEN},
            {"role": "user", "content":
                "Составь ПОЛНОЦЕННУЮ объёмную тренировочную программу по пожеланиям пользователя: "
                "5–8 упражнений в каждый тренировочный день, с прогрессией по неделям. "
                "Если пользователь не указал длительность — сделай 4 недели; не более 12 недель. "
                f"Пожелания:\n{prompt[:4000]}{extra}"},
        ], temperature=0.5)
        data = _extract_json(content)
        return await _ai_build_template(data, current, "ai")

    return await _ai_start_job(current, "generate", _factory)


async def _ai_parse_text(text, current):
    content = await _ai_chat([
        {"role": "system", "content": _AI_SYSTEM},
        {"role": "user", "content":
            "Разбери готовый план тренировок в структуру. Сохрани ВСЕ недели, дни, упражнения, "
            "веса, проценты, подходы и повторы максимально близко к источнику. "
            f"Источник:\n{text[:60000]}"},
    ], temperature=0.1)
    data = _extract_json(content)
    return await _ai_build_template(data, current, "ai")


@api_router.post("/ai/program/parse")
async def ai_parse_program(payload: AiParseReq, current: dict = Depends(get_current_user)):
    """Разбор готового плана (вставленный текст/таблица) — фоновая задача."""
    text = (payload.text or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="Вставьте текст плана (минимум 20 символов)")
    _ai_require_enabled()
    return await _ai_start_job(current, "parse", lambda: _ai_parse_text(text, current))


@api_router.post("/ai/program/parse-file")
async def ai_parse_program_file(file: UploadFile = File(...),
                                current: dict = Depends(get_current_user)):
    """Разбор готового плана из файла (.xlsx / .csv / .txt)."""
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (до 5 МБ)")
    fname = (file.filename or "").lower()
    if fname.endswith(".xlsx"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Не удалось прочитать Excel-файл")
        lines = []
        for ws in wb.worksheets[:5]:
            lines.append(f"### Лист: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = ["" if v is None else str(v) for v in row]
                if any(c.strip() for c in cells):
                    lines.append("\t".join(cells))
        text = "\n".join(lines)
    elif fname.endswith((".csv", ".txt", ".tsv", ".md")):
        text = raw.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=400, detail="Поддерживаются файлы .xlsx, .csv, .txt")
    text = text.strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="Файл пуст или не содержит плана")
    return await _ai_parse_text(text, current)


# ---- Настройки пользователя (streak_mode / единицы) ----
@api_router.patch("/users/{telegram_id}/settings")
async def update_user_settings(telegram_id: int, payload: UserSettingsReq):
    user = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    settings = dict(user.get("settings") or {})
    if payload.streak_mode in ("strict", "lenient"):
        settings["streak_mode"] = payload.streak_mode
    if payload.units in ("kg", "lb"):
        settings["units"] = payload.units
    if payload.default_rest_sec is not None:
        settings["default_rest_sec"] = int(payload.default_rest_sec)
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"settings": settings, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    updated = await db.users.find_one(
        {"telegram_id": telegram_id}, {"_id": 0, "password_hash": 0}
    )
    return updated


# Include the router in the main app
app.include_router(api_router)


# ===========================================================================
# P4 — WebSocket endpoint (/api/ws). Префикс /api обязателен для ingress.
# ===========================================================================
async def _authenticate_ws_token(token: Optional[str]) -> Optional[dict]:
    """Валидация session-token (как Bearer) для WebSocket-хендшейка."""
    if not token:
        return None
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    exp = sess.get("expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except Exception:
            exp = None
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < datetime.now(timezone.utc):
        return None
    return await db.users.find_one(
        {"telegram_id": sess["telegram_id"]}, {"_id": 0, "password_hash": 0}
    )


@app.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    init_data: Optional[str] = Query(default=None),
):
    # 1. Аутентификация: session-token (web/PWA/Telegram) или Telegram initData
    user = await _authenticate_ws_token(token)
    if not user and init_data:
        parsed = validate_telegram_init_data(init_data, TELEGRAM_BOT_TOKEN)
        if parsed:
            tu = parse_telegram_user(parsed)
            if tu and tu.get("id"):
                user = await db.users.find_one(
                    {"telegram_id": tu["id"]}, {"_id": 0, "password_hash": 0}
                )
    if not user:
        await websocket.close(code=4401)  # 4401 — неавторизован
        return

    await websocket.accept()
    tgid = user["telegram_id"]
    name = user.get("first_name") or "Пользователь"
    await manager.register(websocket, tgid, name)
    await manager.join(websocket, f"user:{tgid}")
    await manager.send_personal(websocket, {
        "type": "connected", "room": f"user:{tgid}",
        "payload": {"telegram_id": tgid, "name": name}, "ts": rt_now(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await manager.send_personal(websocket, {"type": "pong", "ts": rt_now()})
            elif mtype == "subscribe":
                plan_id = msg.get("plan_id")
                if plan_id and await _can_access_plan(tgid, plan_id):
                    room = f"plan:{plan_id}"
                    await manager.join(websocket, room)
                    online = manager.presence(room)
                    await manager.send_personal(websocket, {
                        "type": "presence", "room": room,
                        "payload": {"online": online}, "ts": rt_now(),
                    })
                    await manager.broadcast(room, "presence", {"online": online}, exclude=websocket)
            elif mtype == "unsubscribe":
                plan_id = msg.get("plan_id")
                if plan_id:
                    room = f"plan:{plan_id}"
                    await manager.leave(websocket, room)
                    await manager.broadcast(room, "presence", {"online": manager.presence(room)})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"websocket loop error: {e}")
    finally:
        rooms = await manager.disconnect(websocket)
        for room in rooms:
            if room.startswith("plan:"):
                await manager.broadcast(room, "presence", {"online": manager.presence(room)})


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_seed():
    """Идемпотентно создаёт индексы и встроенные данные (упражнения + шаблоны программ)."""
    try:
        await ensure_indexes(db)
    except Exception as e:
        logger.warning(f"ensure_indexes failed: {e}")
    try:
        await ensure_auth_indexes(db)
    except Exception as e:
        logger.warning(f"ensure_auth_indexes failed: {e}")
    try:
        res = await seed_builtins(db)
        logger.info(f"Seed builtins complete: {res}")
    except Exception as e:
        logger.warning(f"seed_builtins failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()