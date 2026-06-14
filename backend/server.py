from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx

from models import (
    Exercise, ExerciseCreate,
    ProgramTemplate, ProgramTemplateCreate,
    Plan, PlanCreate,
)
from seed import seed_builtins, ensure_indexes


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

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
@api_router.post("/plans", response_model=Plan)
async def create_plan(payload: PlanCreate):
    weeks = payload.weeks
    name = payload.name
    source_template_id = payload.template_id

    if payload.template_id:
        tpl = await db.programs.find_one({"id": payload.template_id}, {"_id": 0})
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        weeks = tpl["weeks"]  # снимок структуры
        if not name:
            name = tpl["name"]

    if weeks is None:
        raise HTTPException(status_code=400, detail="Either template_id or weeks must be provided")

    # Один активный план: прежние активные планы спортсмена помечаем завершёнными
    await db.plans.update_many(
        {"athlete_telegram_id": payload.athlete_telegram_id, "status": "active"},
        {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    plan = Plan(
        athlete_telegram_id=payload.athlete_telegram_id,
        coach_telegram_id=payload.coach_telegram_id,
        source_template_id=source_template_id,
        name=name or "Мой план",
        start_date=payload.start_date,
        weeks=weeks,
    )
    doc = plan.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.plans.insert_one(doc)
    logger.info(f"Plan created: {plan.id} for athlete={plan.athlete_telegram_id}")
    return plan


@api_router.get("/plans/active/{telegram_id}", response_model=Optional[Plan])
async def get_active_plan(telegram_id: int):
    doc = await db.plans.find_one(
        {"athlete_telegram_id": telegram_id, "status": "active"},
        {"_id": 0},
    )
    return doc  # может быть None → вернётся null


@api_router.get("/plans/{plan_id}", response_model=Plan)
async def get_plan(plan_id: str):
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")
    return doc


@api_router.get("/plans/{plan_id}/day")
async def get_plan_day(plan_id: str, week: int = 1, day: int = 1):
    """День плана: упражнения + мета. day = 1..7 (Пн..Вс)."""
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    rest_response = {
        "plan_id": plan_id, "week_index": week, "day_index": day,
        "is_rest": True, "title": "День отдыха", "exercises": [],
    }
    week_obj = next((w for w in doc["weeks"] if w["week_index"] == week), None)
    if not week_obj:
        return rest_response
    day_obj = next((d for d in week_obj["days"] if d["day_index"] == day), None)
    if not day_obj:
        return rest_response
    return {"plan_id": plan_id, "week_index": week, **day_obj}


@api_router.get("/plans/{plan_id}/week-progress")
async def get_week_progress(plan_id: str, week: int = 1):
    """Прогресс/расписание по дням недели (для колец в селекторе)."""
    doc = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Plan not found")

    week_obj = next((w for w in doc["weeks"] if w["week_index"] == week), None)
    days_map = {}
    if week_obj:
        for d in week_obj["days"]:
            if d.get("is_rest"):
                continue
            planned_sets = sum(int(e.get("target_sets", 0)) for e in d.get("exercises", []))
            days_map[d["day_index"]] = {
                "title": d.get("title", ""),
                "exercise_count": len(d.get("exercises", [])),
                "planned_sets": planned_sets,
            }

    days = []
    for di in range(1, 8):
        info = days_map.get(di)
        if info:
            days.append({
                "day_index": di, "is_workout": True, "title": info["title"],
                "exercise_count": info["exercise_count"], "planned_sets": info["planned_sets"],
                "completed_sets": 0, "progress_pct": 0,  # Phase 2: реальные данные из сессий
            })
        else:
            days.append({
                "day_index": di, "is_workout": False, "title": "Отдых",
                "exercise_count": 0, "planned_sets": 0,
                "completed_sets": 0, "progress_pct": 0,
            })
    return {"plan_id": plan_id, "week_index": week, "days": days}


# Include the router in the main app
app.include_router(api_router)

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
        res = await seed_builtins(db)
        logger.info(f"Seed builtins complete: {res}")
    except Exception as e:
        logger.warning(f"seed_builtins failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()