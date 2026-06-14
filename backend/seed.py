"""
TrainWithBrain — идемпотентное сидирование Фазы 1.

Создаёт встроенный справочник упражнений и библиотеку готовых программ.
Идемпотентность достигается детерминированными UUID (uuid5 от slug) и upsert по id.

ВАЖНО про индексацию дней: day_index = 1..7 соответствует Пн..Вс
(совпадает с маппингом фронтенда: ((JS getDay()+6)%7)+1).
Дни, отсутствующие в неделе, считаются днями отдыха.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

# Пространство имён для детерминированных UUID встроенных сущностей
TWB_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "trainwithbrain.builtin")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def builtin_id(kind: str, slug: str) -> str:
    return str(uuid.uuid5(TWB_NAMESPACE, f"{kind}:{slug}"))


# ---------------------------------------------------------------------------
# Справочник встроенных упражнений: (slug, name, muscle_groups, equipment, category)
# ---------------------------------------------------------------------------
BUILTIN_EXERCISES = [
    ("back-squat", "Приседания со штангой", ["legs", "glutes"], "barbell", "compound"),
    ("front-squat", "Фронтальные приседания", ["legs", "glutes"], "barbell", "compound"),
    ("bench-press", "Жим лёжа", ["chest", "triceps", "shoulders"], "barbell", "compound"),
    ("incline-bench-press", "Жим лёжа на наклонной", ["chest", "shoulders"], "barbell", "compound"),
    ("deadlift", "Становая тяга", ["back", "legs", "glutes"], "barbell", "compound"),
    ("romanian-deadlift", "Румынская тяга", ["hamstrings", "glutes"], "barbell", "compound"),
    ("overhead-press", "Жим стоя (армейский)", ["shoulders", "triceps"], "barbell", "compound"),
    ("barbell-row", "Тяга штанги в наклоне", ["back", "biceps"], "barbell", "compound"),
    ("pull-up", "Подтягивания", ["back", "biceps"], "bodyweight", "compound"),
    ("lat-pulldown", "Тяга верхнего блока", ["back", "biceps"], "machine", "compound"),
    ("dumbbell-press", "Жим гантелей лёжа", ["chest", "triceps"], "dumbbell", "compound"),
    ("dumbbell-row", "Тяга гантели одной рукой", ["back", "biceps"], "dumbbell", "compound"),
    ("leg-press", "Жим ногами", ["legs", "glutes"], "machine", "compound"),
    ("lunges", "Выпады", ["legs", "glutes"], "dumbbell", "compound"),
    ("leg-curl", "Сгибание ног", ["hamstrings"], "machine", "isolation"),
    ("leg-extension", "Разгибание ног", ["quads"], "machine", "isolation"),
    ("calf-raise", "Подъёмы на носки", ["calves"], "machine", "isolation"),
    ("biceps-curl", "Подъём на бицепс", ["biceps"], "dumbbell", "isolation"),
    ("triceps-pushdown", "Разгибание на трицепс", ["triceps"], "machine", "isolation"),
    ("lateral-raise", "Махи в стороны", ["shoulders"], "dumbbell", "isolation"),
    ("face-pull", "Тяга к лицу", ["shoulders", "back"], "cable", "isolation"),
    ("plank", "Планка", ["core"], "bodyweight", "isolation"),
    ("hanging-leg-raise", "Подъём ног в висе", ["core"], "bodyweight", "isolation"),
    ("dips", "Отжимания на брусьях", ["chest", "triceps"], "bodyweight", "compound"),
]


def _exercise_doc(slug, name, muscles, equipment, category) -> dict:
    return {
        "id": builtin_id("exercise", slug),
        "slug": slug,
        "name": name,
        "muscle_groups": muscles,
        "equipment": equipment,
        "category": category,
        "is_builtin": True,
        "owner_telegram_id": None,
        "created_at": _iso_now(),
    }


# ---------------------------------------------------------------------------
# Хелперы построения шаблонов
# ---------------------------------------------------------------------------
def _ex(slug, name, sets, reps, weight=None, weight_type="kg", rpe=None, rest=120, order=0):
    return {
        "exercise_id": builtin_id("exercise", slug),
        "exercise_name": name,
        "order": order,
        "target_sets": sets,
        "target_reps": reps,
        "target_weight": weight,
        "weight_type": weight_type,
        "target_rpe": rpe,
        "rest_seconds": rest,
        "notes": None,
    }


def _day(day_index, title, exercises):
    for i, e in enumerate(exercises):
        e["order"] = i
    return {"day_index": day_index, "title": title, "is_rest": False, "exercises": exercises}


def _replicate_weeks(day_factory, weeks_count):
    """day_factory(week_index) -> list[ProgramDay dict]; возвращает список недель."""
    return [
        {"week_index": w, "days": day_factory(w)}
        for w in range(1, weeks_count + 1)
    ]


def _template_doc(slug, name, description, author, level, goal, days_per_week, tags, weeks):
    return {
        "id": builtin_id("program", slug),
        "slug": slug,
        "name": name,
        "description": description,
        "author": author,
        "level": level,
        "goal": goal,
        "days_per_week": days_per_week,
        "weeks_count": len(weeks),
        "weeks": weeks,
        "is_builtin": True,
        "owner_telegram_id": None,
        "tags": tags,
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
    }


# --- Шаблон 1: Full Body для новичка (3 дня/нед, 4 недели) ---
def _full_body_days(week):
    return [
        _day(1, "День A — Низ + жим", [
            _ex("back-squat", "Приседания со штангой", 3, "5", rest=180),
            _ex("bench-press", "Жим лёжа", 3, "5", rest=180),
            _ex("barbell-row", "Тяга штанги в наклоне", 3, "8", rest=120),
        ]),
        _day(3, "День B — Тяга + жим стоя", [
            _ex("deadlift", "Становая тяга", 1, "5", rest=240),
            _ex("overhead-press", "Жим стоя (армейский)", 3, "5", rest=150),
            _ex("lat-pulldown", "Тяга верхнего блока", 3, "10", rest=120),
        ]),
        _day(5, "День C — Низ + подсобка", [
            _ex("back-squat", "Приседания со штангой", 3, "5", rest=180),
            _ex("incline-bench-press", "Жим лёжа на наклонной", 3, "8", rest=150),
            _ex("biceps-curl", "Подъём на бицепс", 3, "12", rest=90),
        ]),
    ]


# --- Шаблон 2: Upper/Lower (4 дня/нед, 4 недели), гипертрофия ---
def _upper_lower_days(week):
    return [
        _day(1, "Верх A", [
            _ex("bench-press", "Жим лёжа", 4, "8", rest=120),
            _ex("barbell-row", "Тяга штанги в наклоне", 4, "8", rest=120),
            _ex("overhead-press", "Жим стоя (армейский)", 3, "10", rest=90),
            _ex("biceps-curl", "Подъём на бицепс", 3, "12", rest=60),
            _ex("triceps-pushdown", "Разгибание на трицепс", 3, "12", rest=60),
        ]),
        _day(2, "Низ A", [
            _ex("back-squat", "Приседания со штангой", 4, "8", rest=150),
            _ex("romanian-deadlift", "Румынская тяга", 3, "10", rest=120),
            _ex("leg-press", "Жим ногами", 3, "12", rest=120),
            _ex("calf-raise", "Подъёмы на носки", 4, "15", rest=60),
        ]),
        _day(4, "Верх B", [
            _ex("incline-bench-press", "Жим лёжа на наклонной", 4, "8", rest=120),
            _ex("pull-up", "Подтягивания", 4, "8", weight_type="bodyweight", rest=120),
            _ex("lateral-raise", "Махи в стороны", 4, "15", rest=60),
            _ex("dumbbell-row", "Тяга гантели одной рукой", 3, "10", rest=90),
        ]),
        _day(5, "Низ B", [
            _ex("deadlift", "Становая тяга", 3, "5", rest=180),
            _ex("lunges", "Выпады", 3, "12", rest=90),
            _ex("leg-curl", "Сгибание ног", 3, "12", rest=60),
            _ex("hanging-leg-raise", "Подъём ног в висе", 3, "12", weight_type="bodyweight", rest=60),
        ]),
    ]


# --- Шаблон 3: Powerlifting Peaking (4 дня/нед, 3 недели), проценты от 1ПМ ---
def _powerlifting_days(week):
    # Прогрессия по неделям: 75% -> 82% -> 90%
    pct = {1: 75.0, 2: 82.0, 3: 90.0}[week]
    return [
        _day(1, "Присед (тяжёлый)", [
            _ex("back-squat", "Приседания со штангой", 5, "3", weight=pct, weight_type="percent_1rm", rest=240),
            _ex("leg-press", "Жим ногами", 3, "8", rest=120),
            _ex("plank", "Планка", 3, "60 сек", weight_type="bodyweight", rest=60),
        ]),
        _day(2, "Жим (тяжёлый)", [
            _ex("bench-press", "Жим лёжа", 5, "3", weight=pct, weight_type="percent_1rm", rest=240),
            _ex("overhead-press", "Жим стоя (армейский)", 3, "6", rest=150),
            _ex("triceps-pushdown", "Разгибание на трицепс", 4, "10", rest=60),
        ]),
        _day(4, "Тяга (тяжёлая)", [
            _ex("deadlift", "Становая тяга", 4, "3", weight=pct, weight_type="percent_1rm", rest=240),
            _ex("barbell-row", "Тяга штанги в наклоне", 3, "8", rest=120),
            _ex("pull-up", "Подтягивания", 3, "8", weight_type="bodyweight", rest=120),
        ]),
        _day(5, "Жим (объёмный)", [
            _ex("bench-press", "Жим лёжа", 4, "6", weight=round(pct - 15, 1), weight_type="percent_1rm", rest=180),
            _ex("incline-bench-press", "Жим лёжа на наклонной", 3, "8", rest=120),
            _ex("dips", "Отжимания на брусьях", 3, "10", weight_type="bodyweight", rest=90),
        ]),
    ]


def _builtin_templates():
    return [
        _template_doc(
            "full-body-beginner",
            "Full Body для новичка",
            "Базовая программа на всё тело 3 раза в неделю. Линейная прогрессия, упор на технику базовых движений.",
            "TWB", "beginner", "strength", 3, ["новичок", "база", "сила"],
            _replicate_weeks(_full_body_days, 4),
        ),
        _template_doc(
            "upper-lower-hypertrophy",
            "Upper/Lower (гипертрофия)",
            "Сплит верх/низ 4 раза в неделю для набора мышечной массы.",
            "TWB", "intermediate", "hypertrophy", 4, ["масса", "сплит", "гипертрофия"],
            _replicate_weeks(_upper_lower_days, 4),
        ),
        _template_doc(
            "powerlifting-peaking",
            "Powerlifting Peaking",
            "3-недельный подводящий цикл к максимумам в приседе, жиме и тяге (проценты от 1ПМ).",
            "TWB", "advanced", "powerlifting", 4, ["пауэрлифтинг", "1ПМ", "пик"],
            _replicate_weeks(_powerlifting_days, 3),
        ),
    ]


# ---------------------------------------------------------------------------
# Точка входа: идемпотентное сидирование
# ---------------------------------------------------------------------------
async def seed_builtins(db) -> dict:
    """Создаёт/обновляет встроенные упражнения и шаблоны. Идемпотентно (upsert по id)."""
    ex_count = 0
    for slug, name, muscles, equipment, category in BUILTIN_EXERCISES:
        doc = _exercise_doc(slug, name, muscles, equipment, category)
        await db.exercises.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        ex_count += 1

    tpl_count = 0
    for tpl in _builtin_templates():
        await db.programs.update_one({"id": tpl["id"]}, {"$set": tpl}, upsert=True)
        tpl_count += 1

    return {"exercises": ex_count, "templates": tpl_count}


async def ensure_indexes(db) -> None:
    """Создаёт индексы (идемпотентно)."""
    await db.users.create_index("telegram_id", unique=True)
    await db.exercises.create_index("slug")
    await db.exercises.create_index("owner_telegram_id")
    await db.programs.create_index("is_builtin")
    await db.programs.create_index("owner_telegram_id")
    await db.plans.create_index("athlete_telegram_id")
    await db.plans.create_index([("athlete_telegram_id", 1), ("status", 1)])
