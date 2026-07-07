"""
TrainWithBrain — Pydantic-модели Фазы 1 (Программы и Планы).

Конвенции проекта:
- ID — только UUID-строка (str(uuid.uuid4())); для built-in — детерминированный uuid5(slug).
- datetime сериализуется в ISO-строку при записи в Mongo (делается в server.py).
- Модели БД используют ConfigDict(extra="ignore"), чтобы игнорировать лишние поля Mongo (_id и т.п.).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Справочник упражнений
# ---------------------------------------------------------------------------
class ExerciseCreate(BaseModel):
    name: str
    muscle_groups: List[str] = Field(default_factory=list)
    equipment: Optional[str] = None
    category: Optional[str] = None  # compound | isolation
    owner_telegram_id: Optional[int] = None


class Exercise(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    slug: Optional[str] = None
    name: str
    muscle_groups: List[str] = Field(default_factory=list)
    equipment: Optional[str] = None
    category: Optional[str] = None
    is_builtin: bool = False
    owner_telegram_id: Optional[int] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Встроенные структуры программы (embedded)
# ---------------------------------------------------------------------------
class SetScheme(BaseModel):
    """Одна группа рабочих подходов: вес × подходы × повторы."""
    model_config = ConfigDict(extra="ignore")

    weight: Optional[float] = None
    sets: int = 1
    reps: int = 1


class ProgramExercise(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exercise_id: Optional[str] = None
    exercise_slug: Optional[str] = None
    exercise_name: str
    muscle_group: Optional[str] = None    # ключ мышечной группы каталога, напр. "legs"
    difficulty: Optional[str] = None       # "Легко" | "Средне" | "Тяжело" (задаёт тренер)
    order: int = 0
    target_sets: int = 3
    target_reps: str = "10"           # строка: "5", "8-12", "AMRAP"
    target_weight: Optional[float] = None
    weight_type: str = "kg"           # kg | percent_1rm | rpe | bodyweight
    target_rpe: Optional[float] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    sets_scheme: List[SetScheme] = Field(default_factory=list)  # рабочие подходы (вес×подходы×повторы)
    lift_group: Optional[str] = None    # squat | bench | deadlift | null — для масштабирования по 1ПМ
    is_accessory: bool = False          # подсобное упражнение (без веса/подходов)


class ProgramDay(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day_index: int = 1               # порядковый номер дня в неделе (1..N)
    title: str = ""
    is_rest: bool = False
    exercises: List[ProgramExercise] = Field(default_factory=list)


class ProgramWeek(BaseModel):
    model_config = ConfigDict(extra="ignore")

    week_index: int = 1
    published: bool = True   # неделя видна спортсмену (показ «по одной неделе»)
    days: List[ProgramDay] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Шаблон программы (библиотека / конструктор / импорт)
# ---------------------------------------------------------------------------
class ProgramTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    author: Optional[str] = ""
    level: Optional[str] = "beginner"   # beginner | intermediate | advanced
    goal: Optional[str] = "general"     # strength | hypertrophy | powerlifting | general
    days_per_week: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    weeks: List[ProgramWeek] = Field(default_factory=list)
    owner_telegram_id: Optional[int] = None


class ProgramTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    slug: Optional[str] = None
    name: str
    description: Optional[str] = ""
    author: Optional[str] = ""
    level: Optional[str] = "beginner"
    goal: Optional[str] = "general"
    days_per_week: Optional[int] = None
    weeks_count: int = 0
    weeks: List[ProgramWeek] = Field(default_factory=list)
    is_builtin: bool = False
    owner_telegram_id: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    default_one_rep_max: dict = Field(default_factory=dict)  # slug -> кг (референсные максимумы)
    requires_maxes: bool = False                  # требует ввода 1ПМ (присед/жим/тяга) при выборе
    base_maxes: dict = Field(default_factory=dict)  # {squat,bench,deadlift} автора для масштабирования
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Назначенный план (снимок шаблона под конкретного спортсмена)
# ---------------------------------------------------------------------------
class PlanCreate(BaseModel):
    athlete_telegram_id: int
    template_id: Optional[str] = None         # создать из шаблона...
    weeks: Optional[List[ProgramWeek]] = None  # ...или из inline-структуры
    name: Optional[str] = None
    coach_telegram_id: Optional[int] = None
    start_date: Optional[str] = None           # ISO date (YYYY-MM-DD)
    one_rep_max: Optional[dict] = None
    maxes: Optional[dict] = None               # {squat,bench,deadlift} — для масштабирования весов
    training_days: Optional[List[int]] = None  # выбранные дни недели (1=Пн..7=Вс)
    visibility: Optional[str] = None           # draft | published (если не задано — авто по автору)
    prepared_by_coach: bool = False            # план собран тренером заранее


class Plan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    athlete_telegram_id: int
    coach_telegram_id: Optional[int] = None
    source_template_id: Optional[str] = None
    name: str
    status: str = "active"                    # active | paused | completed
    start_date: Optional[str] = None
    current_week: int = 1
    weeks: List[ProgramWeek] = Field(default_factory=list)
    one_rep_max: dict = Field(default_factory=dict)  # slug -> кг (для расчёта %1ПМ)
    maxes: dict = Field(default_factory=dict)        # {squat,bench,deadlift} спортсмена
    training_days: List[int] = Field(default_factory=list)  # выбранные дни недели (1..7)
    visibility: str = "published"             # draft | published (черновик тренера / опубликован)
    published_at: Optional[str] = None        # ISO — когда план показан спортсмену
    prepared_by_coach: bool = False           # план собран тренером заранее
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Связь тренер ↔ спортсмен
# ---------------------------------------------------------------------------
class CoachLink(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    coach_telegram_id: int
    athlete_telegram_id: int
    status: str = "active"   # pending | active | revoked
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Тренировочная сессия (Phase 2): запуск дня тренировки и отметка упражнений
# ---------------------------------------------------------------------------
class SessionSet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    weight: Optional[float] = None
    sets: int = 1
    reps: int = 1
    percent_1rm: Optional[float] = None


class SetLog(BaseModel):
    """Один индивидуальный рабочий подход — для по-подходного логирования факта.

    Инициализируется из плановой схемы (разворотом weight×sets×reps в отдельные
    подходы); при выполнении спортсмен отмечает `done` и может поправить факт.
    вес/повторы этого конкретного подхода."""
    model_config = ConfigDict(extra="ignore")
    weight: Optional[float] = None       # рабочий вес (план → факт)
    reps: int = 0                        # повторы (план → факт)
    percent_1rm: Optional[float] = None  # % от 1ПМ (справочно)
    done: bool = False                   # подход выполнен


class SessionExercise(BaseModel):
    model_config = ConfigDict(extra="ignore")
    order: int = 0
    exercise_id: Optional[str] = None
    exercise_slug: Optional[str] = None
    exercise_name: str
    muscle_group: Optional[str] = None
    muscle_letter: Optional[str] = None
    difficulty: Optional[str] = None
    sets_scheme: List[SessionSet] = Field(default_factory=list)
    plan_sets_scheme: List[SessionSet] = Field(default_factory=list)  # оригинал из плана (для диффа)
    set_logs: List[SetLog] = Field(default_factory=list)  # по-подходный чек-лист (факт)
    rest_seconds: Optional[int] = None   # отдых между подходами (из плана; для таймера)
    tonnage: float = 0
    status: str = "pending"          # pending | in_progress | done | skipped
    comment: Optional[str] = None    # комментарий спортсмена для тренера (виден тренеру)
    edited: bool = False             # упражнение было изменено (название/подходы)
    lift_group: Optional[str] = None # squat | bench | deadlift | null
    is_accessory: bool = False       # подсобное упражнение
    # --- P4: авторство и подтверждение (real-time co-scribe) ---
    filled_by: Optional[str] = None        # "athlete" | "coach" — кто отметил факт
    coach_confirmed: bool = False          # тренер подтвердил это упражнение
    confirmed_by: Optional[int] = None      # telegram_id тренера
    confirmed_at: Optional[str] = None       # ISO-время подтверждения


class WorkoutSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    plan_id: str
    athlete_telegram_id: int
    coach_telegram_id: Optional[int] = None
    week_index: int = 1
    day_index: int = 1
    date: Optional[str] = None
    title: str = ""
    status: str = "in_progress"      # in_progress | finished | aborted
    paused: bool = False
    started_at: Optional[datetime] = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    exercises: List[SessionExercise] = Field(default_factory=list)
    # --- P4: подтверждение всей тренировки тренером + метка последнего события ---
    coach_confirmed: bool = False
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[str] = None
    last_event_at: Optional[str] = None
    # --- P7: замороженный снимок статистики тренировки (заполняется при finish) ---
    stats: Optional[dict] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SessionStartReq(BaseModel):
    plan_id: str
    athlete_telegram_id: int
    week: int = 1
    day: int = 1
    date: Optional[str] = None      # ISO YYYY-MM-DD — календарная дата тренировки (по выбранному дню)


# ---------------------------------------------------------------------------
# P2.1 — Пропуски/переносы тренировочных дней плана (plan_day_marks)
# ---------------------------------------------------------------------------
class PlanDayMark(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    plan_id: str
    athlete_telegram_id: int
    week_index: int
    day_index: int
    status: str = "skipped"           # skipped | missed | rescheduled | excused
    reason: Optional[str] = None
    rescheduled_to: Optional[str] = None   # ISO date (для переноса)
    marked_by: Optional[int] = None        # telegram_id того, кто пометил
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class DaySkipReq(BaseModel):
    week: int
    day: int
    reason: Optional[str] = None
    marked_by: Optional[int] = None


class DayRescheduleReq(BaseModel):
    week: int
    day: int
    rescheduled_to: str                    # ISO date YYYY-MM-DD
    reason: Optional[str] = None
    marked_by: Optional[int] = None


class DayMarkReq(BaseModel):
    status: str                            # excused | missed | skipped
    reason: Optional[str] = None
    marked_by: Optional[int] = None


class UserSettingsReq(BaseModel):
    streak_mode: Optional[str] = None      # strict | lenient
    units: Optional[str] = None            # kg | lb
    default_rest_sec: Optional[int] = None
