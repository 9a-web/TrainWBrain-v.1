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
import os
import json
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
    # --- Соревновательные вариации (пауэрлифтинг) ---
    ("squat-competition", "Присед (Соревновательный)", ["legs", "glutes"], "barbell", "compound"),
    ("squat-paused", "Присед (с паузой)", ["legs", "glutes"], "barbell", "compound"),
    ("bench-no-legs", "Жим лёжа (без ног)", ["chest", "triceps"], "barbell", "compound"),
    ("close-grip-bench", "Жим узким хватом", ["triceps", "chest"], "barbell", "compound"),
    ("deadlift-competition", "Становая тяга (Соревновательная)", ["back", "legs", "glutes"], "barbell", "compound"),
]

# Праймари-мышца упражнения по slug (для расчёта буквы группы)
EX_MUSCLE = {slug: muscles[0] for slug, _n, muscles, _e, _c in BUILTIN_EXERCISES}

# Мышечная группа -> русская буква
MUSCLE_LETTER = {
    "legs": "Н", "quads": "Н", "hamstrings": "Н", "glutes": "Н", "calves": "Н",
    "chest": "Г",
    "back": "С", "lats": "С",
    "shoulders": "П",
    "biceps": "Р", "triceps": "Р",
    "core": "К",
}
# Порядок отображения букв в сводной «Группе»
LETTER_ORDER = ["Н", "Г", "С", "П", "Р", "К"]


def muscle_letter(muscle):
    return MUSCLE_LETTER.get(muscle or "", "")


def group_letters(muscles):
    """Список ключей мышц -> строка вида 'Н+Г+С' (уникальные буквы в заданном порядке)."""
    seen = []
    for m in muscles:
        ltr = muscle_letter(m)
        if ltr and ltr not in seen:
            seen.append(ltr)
    seen.sort(key=lambda x: LETTER_ORDER.index(x) if x in LETTER_ORDER else 99)
    return "+".join(seen)


def percent_of(weight, slug, one_rep_max):
    """Процент от 1ПМ: weight / 1ПМ * 100 (округлённо). None, если нет данных."""
    if weight is None or not one_rep_max:
        return None
    orm = one_rep_max.get(slug)
    if not orm:
        return None
    return round(weight / orm * 100)


def scheme_tonnage(sets_scheme):
    """Тоннаж по схеме подходов: сумма(вес * подходы * повторы)."""
    total = 0.0
    for s in sets_scheme or []:
        w = s.get("weight")
        if w:
            total += w * (s.get("sets") or 0) * (s.get("reps") or 0)
    return round(total)


def _exercise_doc(slug, name, muscles, equipment, category) -> dict:
    return {
        "id": builtin_id("exercise", slug),
        "slug": slug,
        "name": name,
        "muscle_groups": muscles,
        "equipment": equipment,
        "category": category,
        "weight_type": "bodyweight" if equipment == "bodyweight" else "kg",
        "is_builtin": True,
        "owner_telegram_id": None,
        "created_at": _iso_now(),
    }


# ---------------------------------------------------------------------------
# Хелперы построения шаблонов
# ---------------------------------------------------------------------------
def _ex(slug, name, sets=3, reps="10", weight=None, weight_type="kg", rpe=None,
        rest=120, order=0, scheme=None, difficulty=None):
    """Упражнение программы. scheme = [(weight, sets, reps), ...] для многоподходных схем."""
    if scheme:
        sets_scheme = [{"weight": w, "sets": s, "reps": r} for (w, s, r) in scheme]
        first = scheme[0]
        t_weight, t_sets, t_reps = first[0], first[1], str(first[2])
    else:
        sets_scheme = []
        t_weight, t_sets, t_reps = weight, sets, str(reps)
    return {
        "exercise_id": builtin_id("exercise", slug),
        "exercise_slug": slug,
        "exercise_name": name,
        "muscle_group": EX_MUSCLE.get(slug),
        "difficulty": difficulty,
        "order": order,
        "target_sets": t_sets,
        "target_reps": t_reps,
        "target_weight": t_weight,
        "weight_type": weight_type,
        "target_rpe": rpe,
        "rest_seconds": rest,
        "notes": None,
        "sets_scheme": sets_scheme,
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


def _template_doc(slug, name, description, author, level, goal, days_per_week, tags, weeks,
                  default_one_rep_max=None):
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
        "default_one_rep_max": default_one_rep_max or {},
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


# --- Шаблон 3: Powerlifting Peaking (4 дня/нед, 3 недели), вес + %1ПМ ---
# Референсные максимумы (1ПМ) для расчёта процентов на экране спортсмена.
PL_ONE_REP_MAX = {
    "back-squat": 170, "squat-competition": 170, "squat-paused": 170, "front-squat": 150,
    "bench-press": 140, "bench-no-legs": 140, "close-grip-bench": 130,
    "incline-bench-press": 120, "overhead-press": 95,
    "deadlift": 200, "deadlift-competition": 200, "romanian-deadlift": 180, "barbell-row": 110,
}


def _powerlifting_days(week):
    return [
        # День 1 (Пн) — тяжёлый микс (как на макете)
        _day(1, "Тяжёлый день", [
            _ex("squat-competition", "Присед (Соревновательный)",
                scheme=[(160, 1, 3), (145, 3, 4)], difficulty="Тяжело", rest=240),
            _ex("bench-no-legs", "Жим лёжа (без ног)",
                scheme=[(127.5, 1, 3), (115, 4, 4)], difficulty="Тяжело", rest=240),
            _ex("squat-paused", "Присед (с паузой)",
                scheme=[(160, 1, 3), (142.5, 3, 4)], difficulty="Тяжело", rest=240),
            _ex("deadlift", "Становая тяга",
                scheme=[(180, 1, 3), (160, 3, 4)], difficulty="Тяжело", rest=240),
            _ex("close-grip-bench", "Жим узким хватом",
                scheme=[(100, 4, 6)], difficulty="Средне", rest=150),
            _ex("barbell-row", "Тяга штанги в наклоне",
                scheme=[(90, 4, 8)], difficulty="Средне", rest=120),
            _ex("hanging-leg-raise", "Подъём ног в висе",
                scheme=[(None, 3, 12)], weight_type="bodyweight", difficulty="Легко", rest=60),
        ]),
        # День 2 (Вт) — жим объёмный
        _day(2, "Жим (объёмный)", [
            _ex("bench-press", "Жим лёжа",
                scheme=[(115, 5, 5)], difficulty="Средне", rest=180),
            _ex("incline-bench-press", "Жим лёжа на наклонной",
                scheme=[(90, 4, 8)], difficulty="Средне", rest=120),
            _ex("close-grip-bench", "Жим узким хватом",
                scheme=[(95, 3, 8)], difficulty="Средне", rest=120),
            _ex("lateral-raise", "Махи в стороны",
                scheme=[(12, 4, 15)], difficulty="Легко", rest=60),
        ]),
        # День 4 (Чт) — тяга тяжёлая
        _day(4, "Тяга (тяжёлая)", [
            _ex("deadlift-competition", "Становая тяга (Соревновательная)",
                scheme=[(185, 1, 2), (170, 3, 3)], difficulty="Тяжело", rest=240),
            _ex("barbell-row", "Тяга штанги в наклоне",
                scheme=[(95, 4, 6)], difficulty="Средне", rest=120),
            _ex("pull-up", "Подтягивания",
                scheme=[(None, 4, 8)], weight_type="bodyweight", difficulty="Средне", rest=120),
            _ex("plank", "Планка",
                scheme=[(None, 3, 60)], weight_type="bodyweight", difficulty="Легко", rest=60),
        ]),
        # День 5 (Пт) — присед объёмный
        _day(5, "Присед (объёмный)", [
            _ex("back-squat", "Приседания со штангой",
                scheme=[(135, 5, 5)], difficulty="Средне", rest=180),
            _ex("front-squat", "Фронтальные приседания",
                scheme=[(100, 3, 6)], difficulty="Средне", rest=150),
            _ex("leg-press", "Жим ногами",
                scheme=[(200, 3, 10)], difficulty="Средне", rest=120),
            _ex("leg-curl", "Сгибание ног",
                scheme=[(40, 3, 12)], difficulty="Легко", rest=60),
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
            "3-недельный подводящий цикл к максимумам в приседе, жиме и тяге (вес и %1ПМ).",
            "TWB", "advanced", "powerlifting", 4, ["пауэрлифтинг", "1ПМ", "пик"],
            _replicate_weeks(_powerlifting_days, 3),
            default_one_rep_max=PL_ONE_REP_MAX,
        ),
    ]


# ---------------------------------------------------------------------------
# Точка входа: идемпотентное сидирование
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Импортированные шаблоны из JSON (seed_data/*.json) — напр. Excel-импорт
# ---------------------------------------------------------------------------
SEED_DATA_DIR = os.path.join(os.path.dirname(__file__), "seed_data")


def _imported_templates():
    docs = []
    if not os.path.isdir(SEED_DATA_DIR):
        return docs
    for fn in sorted(os.listdir(SEED_DATA_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(SEED_DATA_DIR, fn), encoding="utf-8") as f:
                tpl = json.load(f)
        except Exception:
            continue
        slug = tpl.get("slug") or fn[:-5]
        weeks = tpl.get("weeks", [])
        docs.append({
            "id": builtin_id("program", slug),
            "slug": slug,
            "name": tpl.get("name", slug),
            "description": tpl.get("description", ""),
            "author": tpl.get("author", "TWB"),
            "level": tpl.get("level", "advanced"),
            "goal": tpl.get("goal", "powerlifting"),
            "days_per_week": tpl.get("days_per_week"),
            "weeks_count": tpl.get("weeks_count") or len(weeks),
            "weeks": weeks,
            "is_builtin": True,
            "owner_telegram_id": None,
            "tags": tpl.get("tags", []),
            "default_one_rep_max": tpl.get("default_one_rep_max", {}),
            "requires_maxes": bool(tpl.get("requires_maxes", False)),
            "base_maxes": tpl.get("base_maxes", {}),
            "created_at": _iso_now(),
            "updated_at": _iso_now(),
        })
    return docs


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

    for tpl in _imported_templates():
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
    await db.workout_sessions.create_index("athlete_telegram_id")
    await db.workout_sessions.create_index([("plan_id", 1), ("week_index", 1), ("day_index", 1)])
    # P3 — режим тренера
    await db.users.create_index("invite_code", unique=True, sparse=True)
    await db.plans.create_index([("coach_telegram_id", 1), ("status", 1)])
    await db.coach_links.create_index([("coach_telegram_id", 1), ("athlete_telegram_id", 1)], unique=True)
    await db.coach_links.create_index("athlete_telegram_id")
    # P7 / P2.1 — статистика и пропуски тренировок
    await db.workout_sessions.create_index([("athlete_telegram_id", 1), ("status", 1)])
    await db.workout_sessions.create_index("finished_at")
    await db.plan_day_marks.create_index(
        [("plan_id", 1), ("week_index", 1), ("day_index", 1)], unique=True
    )
    await db.plan_day_marks.create_index("athlete_telegram_id")
