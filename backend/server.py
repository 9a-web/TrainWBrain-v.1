from fastapi import FastAPI, APIRouter, HTTPException, Body, Depends, Header, Cookie, Response, WebSocket, WebSocketDisconnect, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
import copy
import json
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, date, timedelta
import httpx

from models import (
    Exercise, ExerciseCreate,
    ProgramTemplate, ProgramTemplateCreate,
    Plan, PlanCreate,
    WorkoutSession, SessionStartReq,
    CoachLink,
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


# ---- Шаблоны программ (библиотека / конструктор) ----
@api_router.get("/programs/templates", response_model=List[ProgramTemplate])
async def list_templates(level: Optional[str] = None, goal: Optional[str] = None, owner: Optional[int] = None):
    filt = {}
    if level:
        filt["level"] = level
    if goal:
        filt["goal"] = goal
    if owner is not None:
        filt["$or"] = [{"is_builtin": True}, {"owner_telegram_id": owner}]
    else:
        filt["is_builtin"] = True
    docs = await db.programs.find(filt, {"_id": 0}).to_list(1000)
    return docs


@api_router.get("/programs/templates/{template_id}", response_model=ProgramTemplate)
async def get_template(template_id: str):
    doc = await db.programs.find_one({"id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@api_router.post("/programs/templates", response_model=ProgramTemplate)
async def create_template(payload: ProgramTemplateCreate):
    tpl = ProgramTemplate(
        **payload.model_dump(),
        is_builtin=False,
        weeks_count=len(payload.weeks or []),
    )
    doc = tpl.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.programs.insert_one(doc)
    logger.info(f"Custom template created: {tpl.name} (owner={tpl.owner_telegram_id})")
    return tpl


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
async def create_plan(payload: PlanCreate):
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
    await db.plans.update_many(
        {"athlete_telegram_id": payload.athlete_telegram_id, "status": "active"},
        {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Видимость: тренер, готовящий план другому спортсмену → по умолчанию черновик
    coach_id = payload.coach_telegram_id
    is_coach_prepared = bool(coach_id and coach_id != payload.athlete_telegram_id)
    if payload.visibility in ("draft", "published"):
        visibility = payload.visibility
    else:
        visibility = "draft" if is_coach_prepared else "published"
    prepared_by_coach = payload.prepared_by_coach or is_coach_prepared
    now_iso = datetime.now(timezone.utc).isoformat()

    plan = Plan(
        athlete_telegram_id=payload.athlete_telegram_id,
        coach_telegram_id=payload.coach_telegram_id,
        source_template_id=source_template_id,
        name=name or "Мой план",
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
        return None
    # Черновик тренера: спортсмену не показываем содержимое («план готовится»)
    if doc.get("visibility") == "draft":
        doc["weeks"] = []
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

    # У спортсмена один активный тренер
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
        plan = await db.plans.find_one(
            {"athlete_telegram_id": a_id, "status": "active"}, {"_id": 0}
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


@api_router.get("/coach/{telegram_id}/clients/{athlete_id}/plan", response_model=Optional[Plan])
async def coach_client_plan(telegram_id: int, athlete_id: int):
    """Активный план подопечного (полный, в т.ч. черновик — тренер видит всегда)."""
    await _assert_coach_of(telegram_id, athlete_id)
    doc = await db.plans.find_one(
        {"athlete_telegram_id": athlete_id, "status": "active"}, {"_id": 0}
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
async def set_plan_visibility(plan_id: str, payload: VisibilityReq):
    vis = (payload.visibility or "").strip().lower()
    if vis not in ("draft", "published"):
        raise HTTPException(status_code=400, detail="visibility должен быть draft или published")
    plan = await _get_plan_or_404(plan_id)
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"visibility": vis, "updated_at": now}
    if vis == "published" and not plan.get("published_at"):
        set_fields["published_at"] = now
    await db.plans.update_one({"id": plan_id}, {"$set": set_fields})
    updated = await _get_plan_or_404(plan_id)
    await _rt_plan(plan_id, "plan.published", {"visibility": vis})
    await _notify_user(updated.get("athlete_telegram_id"), "plan.published",
                       {"plan_id": plan_id, "visibility": vis})
    return updated


@api_router.patch("/plans/{plan_id}/weeks/{week}/publish", response_model=Plan)
async def publish_plan_week(plan_id: str, week: int, payload: WeekPublishReq):
    plan = await _get_plan_or_404(plan_id)
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
async def set_plan_training_days(plan_id: str, payload: TrainingDaysReq):
    days = payload.training_days or []
    if any((not isinstance(d, int)) or d < 1 or d > 7 for d in days):
        raise HTTPException(status_code=400, detail="training_days: числа 1..7")
    norm = sorted(set(int(d) for d in days))
    plan = await _get_plan_or_404(plan_id)
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
    return await _get_plan_or_404(plan_id)


@api_router.patch("/plans/{plan_id}", response_model=Plan)
async def update_plan_meta(plan_id: str, payload: PlanMetaReq):
    """Переименовать план / задать текущую неделю / дату старта."""
    await _get_plan_or_404(plan_id)
    set_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.name is not None and payload.name.strip():
        set_fields["name"] = payload.name.strip()
    if payload.current_week is not None:
        set_fields["current_week"] = max(1, int(payload.current_week))
    if payload.start_date is not None:
        set_fields["start_date"] = payload.start_date
    await db.plans.update_one({"id": plan_id}, {"$set": set_fields})
    return await _get_plan_or_404(plan_id)


@api_router.put("/plans/{plan_id}/day", response_model=Plan)
async def upsert_plan_day(plan_id: str, payload: PlanDayUpsertReq):
    """Создать/изменить день недели (день = слот дня недели 1..7)."""
    if payload.day < 1 or payload.day > 7:
        raise HTTPException(status_code=400, detail="day: 1..7")
    plan = await _get_plan_or_404(plan_id)
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
async def delete_plan_day(plan_id: str, week: int, day: int):
    plan = await _get_plan_or_404(plan_id)
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
async def upsert_plan_exercise(plan_id: str, payload: PlanExerciseReq):
    """Добавить (order=None) или изменить (order задан) упражнение в дне."""
    plan = await _get_plan_or_404(plan_id)
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
async def delete_plan_exercise(plan_id: str, week: int, day: int, order: int):
    plan = await _get_plan_or_404(plan_id)
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
async def add_plan_week(plan_id: str):
    """Добавить пустую неделю в конец плана."""
    plan = await _get_plan_or_404(plan_id)
    weeks = plan.get("weeks") or []
    next_index = (max((w.get("week_index", 0) for w in weeks), default=0)) + 1
    weeks.append({"week_index": next_index, "published": True, "days": []})
    return await _save_plan_weeks(plan_id, weeks)


@api_router.delete("/plans/{plan_id}/week", response_model=Plan)
async def delete_plan_week(plan_id: str, week: int):
    """Удалить неделю и пере-нумеровать оставшиеся (1..N)."""
    plan = await _get_plan_or_404(plan_id)
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
    return await _get_plan_or_404(plan_id)




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
        "tonnage": scheme_tonnage(sets),
        "status": status,
        "comment": pe.get("comment"),
        "edited": pe.get("edited", False),
        "lift_group": pe.get("lift_group"),
        "is_accessory": is_acc,
        "filled_by": None,
        "coach_confirmed": False,
        "confirmed_by": None,
        "confirmed_at": None,
    }


def _day_group_difficulty(exercises):
    group = group_letters([e.get("muscle_group") for e in exercises])
    diffs = [e.get("difficulty") for e in exercises if e.get("difficulty")]
    difficulty = max(diffs, key=lambda d: _DIFF_RANK.get(d, 0)) if diffs else None
    return group, difficulty


def _build_session_exercises(day_obj, orm):
    ordered = sorted(day_obj.get("exercises", []), key=lambda x: x.get("order", 0))
    exs = [_view_exercise(pe, orm, i) for i, pe in enumerate(ordered)]
    if exs:
        exs[0]["status"] = "in_progress"
    return exs


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
    return {
        "tonnage": tonnage,
        "group": group,
        "difficulty": difficulty,
        "duration_sec": duration_sec,
        "done_count": len(done),
        "skipped_count": len(skipped),
        "total_count": total,
        "progress_pct": progress_pct,
    }


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
async def get_plan_day(plan_id: str, week: int = 1, day: int = 1):
    """День плана: упражнения + мета. day = 1..7 (Пн..Вс)."""
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
async def get_week_progress(plan_id: str, week: int = 1):
    """Прогресс/расписание по дням недели (для колец в селекторе)."""
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    week_obj = next((w for w in (doc.get("weeks") or []) if w.get("week_index") == week), None)
    days_map = {}
    if week_obj:
        for d in (week_obj.get("days") or []):
            if d.get("is_rest"):
                continue
            planned_sets = sum(int(e.get("target_sets", 0) or 0) for e in d.get("exercises", []))
            days_map[d.get("day_index")] = {
                "title": d.get("title", ""),
                "exercise_count": len(d.get("exercises", [])),
                "planned_sets": planned_sets,
            }

    # Сессии этой недели — для реального прогресса колец
    sessions = await db.workout_sessions.find(
        {"plan_id": plan_id, "week_index": week}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    sess_by_day = {s.get("day_index"): s for s in sessions}

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
    return {"plan_id": plan_id, "week_index": week, "days": days}


# ===========================================================================
# Тренировочные сессии (Phase 2)
# ===========================================================================
@api_router.post("/sessions/start")
async def start_session(req: SessionStartReq):
    plan = await db.plans.find_one({"id": req.plan_id}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    existing = await db.workout_sessions.find_one(
        {"plan_id": req.plan_id, "athlete_telegram_id": req.athlete_telegram_id,
         "week_index": req.week, "day_index": req.day, "status": {"$ne": "finished"}},
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
            "message": "У вас уже есть активная тренировка. Завершите её, чтобы начать новую.",
            "session_id": active_other["id"],
            "plan_id": active_other.get("plan_id"),
            "week_index": active_other.get("week_index"),
            "day_index": active_other.get("day_index"),
        })

    week_obj = next((w for w in (plan.get("weeks") or []) if w.get("week_index") == req.week), None)
    day_obj = next((d for d in (week_obj.get("days") or []) if d.get("day_index") == req.day), None) if week_obj else None
    if not day_obj or day_obj.get("is_rest"):
        raise HTTPException(status_code=400, detail="No workout scheduled for this day")

    orm = plan.get("one_rep_max") or {}
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": str(uuid.uuid4()),
        "plan_id": req.plan_id,
        "athlete_telegram_id": req.athlete_telegram_id,
        "coach_telegram_id": plan.get("coach_telegram_id"),
        "week_index": req.week, "day_index": req.day,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "title": day_obj.get("title", ""),
        "status": "in_progress", "paused": False,
        "started_at": now, "finished_at": None,
        "exercises": _build_session_exercises(day_obj, orm),
        "coach_confirmed": False, "confirmed_by": None, "confirmed_at": None,
        "last_event_at": now,
        "created_at": now, "updated_at": now,
    }
    await db.workout_sessions.insert_one(dict(session))
    logger.info(f"Session started: {session['id']} plan={req.plan_id} day={req.day}")
    # Real-time: оповестить комнату плана и лично тренера
    await _rt_session(req.plan_id, "session.started", session)
    await _notify_user(plan.get("coach_telegram_id"), "session.started", {
        "session_id": session["id"], "plan_id": req.plan_id,
        "athlete_telegram_id": req.athlete_telegram_id,
        "week_index": req.week, "day_index": req.day, "title": session["title"],
    })
    return _serialize_session(session)


@api_router.get("/sessions/active")
async def get_active_session(plan_id: str, week: int, day: int, athlete: int):
    s = await db.workout_sessions.find_one(
        {"plan_id": plan_id, "athlete_telegram_id": athlete, "week_index": week, "day_index": day},
        {"_id": 0}, sort=[("created_at", -1)],
    )
    if not s:
        return None
    return _serialize_session(s)


@api_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize_session(s)


@api_router.patch("/sessions/{session_id}/exercise/{order}")
async def update_session_exercise(
    session_id: str,
    order: int,
    action: str,
    actor: str = "athlete",
    by: Optional[int] = None,
):
    """Отметка упражнения (done/skip/reset).

    actor: "athlete" (по умолчанию) или "coach" — кто отмечает. Если actor=="coach",
    проверяем, что `by` (telegram_id тренера) действительно тренер этого спортсмена.
    Заполняется поле `filled_by` для real-time co-scribe.
    """
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if actor == "coach":
        if by is None:
            raise HTTPException(status_code=400, detail="Не указан тренер (by)")
        await _assert_coach_of(by, s["athlete_telegram_id"])

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")

    if action == "done":
        target["status"] = "done"
        target["filled_by"] = actor
    elif action == "skip":
        target["status"] = "skipped"
        target["filled_by"] = actor
    elif action == "reset":
        target["status"] = "pending"
        target["filled_by"] = None
        # Сброс отметки снимает и подтверждение тренера
        target["coach_confirmed"] = False
        target["confirmed_by"] = None
        target["confirmed_at"] = None
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

    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"exercises": exs, "status": status, "finished_at": finished_at,
                  "updated_at": now, "last_event_at": now}},
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


@api_router.patch("/sessions/{session_id}/exercise/{order}/edit")
async def edit_session_exercise(
    session_id: str,
    order: int,
    payload: dict = Body(...),
    actor: str = "athlete",
    by: Optional[int] = None,
):
    """Редактирование упражнения сессии (кнопка ✨): имя и/или схема подходов.

    actor: "athlete" | "coach". Тренер (actor=="coach", by=telegram_id тренера)
    может править упражнение подопечного в реальном времени (co-scribe)."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if actor == "coach":
        if by is None:
            raise HTTPException(status_code=400, detail="Не указан тренер (by)")
        await _assert_coach_of(by, s["athlete_telegram_id"])
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
async def finish_session(session_id: str):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    now = datetime.now(timezone.utc).isoformat()
    finished_at = s.get("finished_at") or now
    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "finished", "finished_at": finished_at, "updated_at": now, "last_event_at": now}},
    )
    s["status"] = "finished"
    s["finished_at"] = finished_at
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.finished", s)
    await _notify_user(s.get("coach_telegram_id"), "session.finished", {
        "session_id": s["id"], "plan_id": s.get("plan_id"),
        "athlete_telegram_id": s["athlete_telegram_id"],
    })
    return _serialize_session(s)


@api_router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str, resume: bool = False):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id}, {"$set": {"paused": (not resume), "updated_at": now, "last_event_at": now}}
    )
    s["paused"] = (not resume)
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.updated", s)
    return _serialize_session(s)


class SessionConfirmReq(BaseModel):
    coach_telegram_id: Optional[int] = None


@api_router.post("/sessions/{session_id}/confirm")
async def confirm_session(session_id: str, payload: SessionConfirmReq = Body(default=None)):
    """Тренер подтверждает выполнение тренировки подопечного (coach_confirmed=true)."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    coach_tgid = payload.coach_telegram_id if payload else None
    if coach_tgid is not None:
        await _assert_coach_of(coach_tgid, s["athlete_telegram_id"])
    now = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "coach_confirmed": True,
            "confirmed_by": coach_tgid,
            "confirmed_at": now,
            "updated_at": now,
        }},
    )
    s["coach_confirmed"] = True
    s["confirmed_by"] = coach_tgid
    s["confirmed_at"] = now
    s["last_event_at"] = now
    await db.workout_sessions.update_one({"id": session_id}, {"$set": {"last_event_at": now}})
    await _rt_session(s.get("plan_id"), "session.confirmed", s)
    await _notify_user(s.get("athlete_telegram_id"), "session.confirmed", {
        "session_id": s["id"], "plan_id": s.get("plan_id"),
    })
    return _serialize_session(s)


@api_router.patch("/sessions/{session_id}/exercise/{order}/confirm")
async def confirm_session_exercise(
    session_id: str, order: int, payload: SessionConfirmReq = Body(default=None)
):
    """Тренер подтверждает выполнение отдельного упражнения подопечного."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    coach_tgid = payload.coach_telegram_id if payload else None
    if coach_tgid is None:
        raise HTTPException(status_code=400, detail="Не указан тренер (coach_telegram_id)")
    await _assert_coach_of(coach_tgid, s["athlete_telegram_id"])

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")

    now = datetime.now(timezone.utc).isoformat()
    # Переключатель: повторное подтверждение снимает отметку тренера
    new_state = not bool(target.get("coach_confirmed"))
    target["coach_confirmed"] = new_state
    target["confirmed_by"] = coach_tgid if new_state else None
    target["confirmed_at"] = now if new_state else None

    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"exercises": exs, "updated_at": now, "last_event_at": now}},
    )
    s["exercises"] = exs
    s["last_event_at"] = now
    await _rt_session(s.get("plan_id"), "session.updated", s)
    return _serialize_session(s)


# ---- Сводная статистика спортсмена (серия/streak) ----
@api_router.get("/stats/{telegram_id}")
async def get_athlete_stats(telegram_id: int):
    sessions = await db.workout_sessions.find(
        {"athlete_telegram_id": telegram_id, "status": "finished"},
        {"_id": 0, "finished_at": 1, "exercises": 1},
    ).to_list(2000)

    dates = set()
    for s in sessions:
        # Засчитываем тренировку только если реально выполнено хотя бы одно упражнение
        # (полностью пропущенная сессия не должна формировать серию/счётчик).
        if not any(e.get("status") == "done" for e in (s.get("exercises") or [])):
            continue
        fa = s.get("finished_at")
        if fa:
            try:
                dates.add(datetime.fromisoformat(fa).date())
            except Exception:
                pass

    streak = 0
    if dates:
        today = datetime.now(timezone.utc).date()
        cur = today if today in dates else (today - timedelta(days=1))
        while cur in dates:
            streak += 1
            cur = cur - timedelta(days=1)

    return {"telegram_id": telegram_id, "streak_days": streak, "total_workouts": len(dates)}


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