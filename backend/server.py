from fastapi import FastAPI, APIRouter, HTTPException, Body
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
import copy
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
)
from seed import (
    seed_builtins, ensure_indexes,
    group_letters, muscle_letter, percent_of, scheme_tonnage,
)


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
def _round_2_5(x):
    """Округление веса до ближайших 2.5 кг."""
    return round(round(float(x) / 2.5) * 2.5, 2)


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
        td = sorted({int(x) for x in training_days if 1 <= int(x) <= 7})
        for w in weeks:
            workout_days = sorted(
                [d for d in w.get("days", []) if not d.get("is_rest")],
                key=lambda d: d.get("day_index", 0),
            )
            for i, d in enumerate(workout_days):
                if i < len(td):
                    d["day_index"] = td[i]

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
        "tonnage": scheme_tonnage(sets),
        "status": status,
        "comment": pe.get("comment"),
        "edited": pe.get("edited", False),
        "lift_group": pe.get("lift_group"),
        "is_accessory": is_acc,
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
    week_obj = next((w for w in doc["weeks"] if w["week_index"] == week), None)
    if not week_obj:
        return rest_response
    day_obj = next((d for d in week_obj["days"] if d["day_index"] == day), None)
    if not day_obj:
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

    week_obj = next((w for w in doc["weeks"] if w["week_index"] == week), None)
    days_map = {}
    if week_obj:
        for d in week_obj["days"]:
            if d.get("is_rest"):
                continue
            planned_sets = sum(int(e.get("target_sets", 0) or 0) for e in d.get("exercises", []))
            days_map[d["day_index"]] = {
                "title": d.get("title", ""),
                "exercise_count": len(d.get("exercises", [])),
                "planned_sets": planned_sets,
            }

    # Сессии этой недели — для реального прогресса колец
    sessions = await db.workout_sessions.find(
        {"plan_id": plan_id, "week_index": week}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    sess_by_day = {s["day_index"]: s for s in sessions}

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

    week_obj = next((w for w in plan["weeks"] if w["week_index"] == req.week), None)
    day_obj = next((d for d in week_obj["days"] if d["day_index"] == req.day), None) if week_obj else None
    if not day_obj or day_obj.get("is_rest"):
        raise HTTPException(status_code=400, detail="No workout scheduled for this day")

    orm = plan.get("one_rep_max") or {}
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": str(uuid.uuid4()),
        "plan_id": req.plan_id,
        "athlete_telegram_id": req.athlete_telegram_id,
        "coach_telegram_id": plan.get("coach_telegram_id"),
        "week_index": req.week, "day_index": req.day, "date": None,
        "title": day_obj.get("title", ""),
        "status": "in_progress", "paused": False,
        "started_at": now, "finished_at": None,
        "exercises": _build_session_exercises(day_obj, orm),
        "created_at": now, "updated_at": now,
    }
    await db.workout_sessions.insert_one(dict(session))
    logger.info(f"Session started: {session['id']} plan={req.plan_id} day={req.day}")
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
async def update_session_exercise(session_id: str, order: int, action: str):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    exs = s["exercises"]
    target = next((e for e in exs if e["order"] == order), None)
    if not target:
        raise HTTPException(status_code=404, detail="Exercise not found")

    if action == "done":
        target["status"] = "done"
    elif action == "skip":
        target["status"] = "skipped"
    elif action == "reset":
        target["status"] = "pending"
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
    if exs and all(e["status"] in ("done", "skipped") for e in exs):
        status = "finished"
        finished_at = finished_at or now

    await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"exercises": exs, "status": status, "finished_at": finished_at, "updated_at": now}},
    )
    s["exercises"] = exs
    s["status"] = status
    s["finished_at"] = finished_at
    return _serialize_session(s)


@api_router.patch("/sessions/{session_id}/exercise/{order}/edit")
async def edit_session_exercise(session_id: str, order: int, payload: dict = Body(...)):
    """Редактирование упражнения сессии (кнопка ✨): имя и/или схема подходов."""
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
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
        {"id": session_id}, {"$set": {"exercises": exs, "updated_at": now}}
    )
    s["exercises"] = exs
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
        {"$set": {"status": "finished", "finished_at": finished_at, "updated_at": now}},
    )
    s["status"] = "finished"
    s["finished_at"] = finished_at
    return _serialize_session(s)


@api_router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str, resume: bool = False):
    s = await db.workout_sessions.find_one({"id": session_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.workout_sessions.update_one(
        {"id": session_id}, {"$set": {"paused": (not resume), "updated_at": now}}
    )
    s["paused"] = (not resume)
    return _serialize_session(s)


# ---- Сводная статистика спортсмена (серия/streak) ----
@api_router.get("/stats/{telegram_id}")
async def get_athlete_stats(telegram_id: int):
    sessions = await db.workout_sessions.find(
        {"athlete_telegram_id": telegram_id, "status": "finished"},
        {"_id": 0, "finished_at": 1},
    ).to_list(2000)

    dates = set()
    for s in sessions:
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