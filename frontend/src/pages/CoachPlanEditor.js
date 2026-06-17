import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import {
  ArrowLeft, Plus, Trash2, Pencil, X, Check, CalendarPlus, Dumbbell,
} from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@/context/UserContext";
import {
  getCoachClientPlan, getUserById,
  updatePlanMeta, upsertPlanDay, deletePlanDay,
  upsertPlanExercise, deletePlanExercise, addPlanWeek, deletePlanWeek,
} from "@/api";
import Portal from "@/components/Portal";
import { haptic, hapticNotify } from "@/lib/platform";
import { useBackButton } from "@/hooks/useTelegramUI";
import "./Coach.css";

const WEEKDAYS = [
  { idx: 1, label: "Пн", full: "Понедельник" },
  { idx: 2, label: "Вт", full: "Вторник" },
  { idx: 3, label: "Ср", full: "Среда" },
  { idx: 4, label: "Чт", full: "Четверг" },
  { idx: 5, label: "Пт", full: "Пятница" },
  { idx: 6, label: "Сб", full: "Суббота" },
  { idx: 7, label: "Вс", full: "Воскресенье" },
];
const weekdayFull = (i) => (WEEKDAYS.find((w) => w.idx === i) || {}).full || `День ${i}`;

const MUSCLE_OPTIONS = [
  { v: "", l: "—" },
  { v: "legs", l: "Ноги" },
  { v: "chest", l: "Грудь" },
  { v: "back", l: "Спина" },
  { v: "shoulders", l: "Плечи" },
  { v: "biceps", l: "Бицепс" },
  { v: "triceps", l: "Трицепс" },
  { v: "core", l: "Кор / Пресс" },
];
const DIFF_OPTIONS = ["", "Легко", "Средне", "Тяжело"];

const fmtSets = (ex) => {
  if (ex.is_accessory) return "подсобное";
  const s = ex.sets_scheme || [];
  if (!s.length) return `${ex.target_sets || "?"}×${ex.target_reps || "?"}`;
  return s
    .map((x) => `${x.weight != null ? x.weight : "—"}×${x.sets}×${x.reps}`)
    .join(", ");
};

/* ---------- Модалка упражнения ---------- */
function ExerciseModal({ initial, onClose, onSave, saving }) {
  const ex = initial || {};
  const [name, setName] = useState(ex.exercise_name || "");
  const [muscle, setMuscle] = useState(ex.muscle_group || "");
  const [difficulty, setDifficulty] = useState(ex.difficulty || "");
  const [isAccessory, setIsAccessory] = useState(!!ex.is_accessory);
  const [rpe, setRpe] = useState(ex.target_rpe != null ? String(ex.target_rpe) : "");
  const [rest, setRest] = useState(ex.rest_seconds != null ? String(ex.rest_seconds) : "");
  const [notes, setNotes] = useState(ex.notes || "");
  const [rows, setRows] = useState(
    (ex.sets_scheme && ex.sets_scheme.length
      ? ex.sets_scheme.map((s) => ({
          weight: s.weight != null ? String(s.weight) : "",
          sets: String(s.sets || 1),
          reps: String(s.reps || 0),
        }))
      : [{ weight: "", sets: "3", reps: "5" }])
  );

  const setRow = (i, key, val) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, [key]: val } : r)));
  const addRow = () => setRows((p) => [...p, { weight: "", sets: "3", reps: "5" }]);
  const delRow = (i) => setRows((p) => (p.length > 1 ? p.filter((_, idx) => idx !== i) : p));

  const canSave = name.trim().length > 0 && !saving;

  const submit = () => {
    if (!canSave) return;
    const body = {
      exercise_name: name.trim(),
      muscle_group: muscle || null,
      difficulty: difficulty || null,
      is_accessory: isAccessory,
      weight_type: "kg",
      target_rpe: rpe ? Number(rpe) : null,
      rest_seconds: rest ? Number(rest) : null,
      notes: notes.trim() || null,
      // сохраняем технические поля для расчёта %1ПМ
      exercise_slug: ex.exercise_slug || null,
      exercise_id: ex.exercise_id || null,
      lift_group: ex.lift_group || null,
    };
    if (!isAccessory) {
      body.sets_scheme = rows.map((r) => ({
        weight: r.weight !== "" ? Number(r.weight) : null,
        sets: Number(r.sets) || 1,
        reps: Number(r.reps) || 0,
      }));
    } else {
      body.sets_scheme = [];
    }
    onSave(body);
  };

  return (
    <Portal>
    <div className="cfg-overlay" onClick={onClose} data-testid="exercise-modal">
      <div className="cfg-modal ed-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="cfg-title">{ex.exercise_name ? "Изменить упражнение" : "Новое упражнение"}</h3>

        <label className="ed-field">
          <span>Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Напр. Жим лёжа" data-testid="ex-name" />
        </label>

        <div className="ed-row2">
          <label className="ed-field">
            <span>Группа мышц</span>
            <select value={muscle} onChange={(e) => setMuscle(e.target.value)} data-testid="ex-muscle">
              {MUSCLE_OPTIONS.map((m) => (<option key={m.v} value={m.v}>{m.l}</option>))}
            </select>
          </label>
          <label className="ed-field">
            <span>Сложность</span>
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} data-testid="ex-diff">
              {DIFF_OPTIONS.map((d) => (<option key={d} value={d}>{d || "—"}</option>))}
            </select>
          </label>
        </div>

        <label className="ed-check">
          <input type="checkbox" checked={isAccessory} onChange={(e) => setIsAccessory(e.target.checked)} data-testid="ex-accessory" />
          <span>Подсобное (без рабочих весов/подходов)</span>
        </label>

        {!isAccessory ? (
          <div className="ed-sets">
            <div className="ed-sets-head">
              <span>Вес, кг</span><span>Подх.</span><span>Повт.</span><span></span>
            </div>
            {rows.map((r, i) => (
              <div className="ed-set-row" key={i}>
                <input type="number" inputMode="decimal" value={r.weight} onChange={(e) => setRow(i, "weight", e.target.value)} placeholder="—" data-testid={`set-weight-${i}`} />
                <input type="number" inputMode="numeric" value={r.sets} onChange={(e) => setRow(i, "sets", e.target.value)} data-testid={`set-sets-${i}`} />
                <input type="number" inputMode="numeric" value={r.reps} onChange={(e) => setRow(i, "reps", e.target.value)} data-testid={`set-reps-${i}`} />
                <button className="ed-set-del" onClick={() => delRow(i)} aria-label="Удалить подход"><X size={15} /></button>
              </div>
            ))}
            <button className="ed-addrow" onClick={addRow} data-testid="add-set-row"><Plus size={14} /> Подход</button>
          </div>
        ) : null}

        <div className="ed-row2">
          <label className="ed-field">
            <span>RPE</span>
            <input type="number" inputMode="decimal" value={rpe} onChange={(e) => setRpe(e.target.value)} placeholder="—" />
          </label>
          <label className="ed-field">
            <span>Отдых, сек</span>
            <input type="number" inputMode="numeric" value={rest} onChange={(e) => setRest(e.target.value)} placeholder="—" />
          </label>
        </div>

        <label className="ed-field">
          <span>Заметка</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Комментарий для спортсмена" />
        </label>

        <div className="cfg-actions">
          <button className="cfg-btn-cancel" onClick={onClose}>Отмена</button>
          <button className="cfg-btn-save" onClick={submit} disabled={!canSave} data-testid="ex-save">
            {saving ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
    </Portal>
  );
}

/* ---------- Модалка дня ---------- */
function DayModal({ mode, used, initial, onClose, onSave, saving }) {
  const [day, setDay] = useState(initial?.day_index || (WEEKDAYS.find((w) => !used.includes(w.idx)) || {}).idx || 1);
  const [title, setTitle] = useState(initial?.title || "");
  const [isRest, setIsRest] = useState(!!initial?.is_rest);
  const isEdit = mode === "edit";

  const submit = () => {
    if (saving) return;
    onSave({ day, title: title.trim() || `День ${day}`, is_rest: isRest });
  };

  return (
    <Portal>
    <div className="cfg-overlay" onClick={onClose} data-testid="day-modal">
      <div className="cfg-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="cfg-title">{isEdit ? "Изменить день" : "Новый день"}</h3>
        {!isEdit ? (
          <div className="cfg-section">
            <div className="cfg-section-title">День недели</div>
            <div className="cfg-days">
              {WEEKDAYS.map((d) => {
                const disabled = used.includes(d.idx);
                return (
                  <button
                    key={d.idx}
                    className={`cfg-day ${day === d.idx ? "active" : ""}`}
                    onClick={() => !disabled && setDay(d.idx)}
                    disabled={disabled}
                    style={disabled ? { opacity: 0.3 } : undefined}
                    data-testid={`day-pick-${d.idx}`}
                  >
                    {d.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="cfg-sub">{weekdayFull(initial?.day_index)}</p>
        )}

        <label className="ed-field">
          <span>Название</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Напр. День ног" data-testid="day-title" />
        </label>

        <label className="ed-check">
          <input type="checkbox" checked={isRest} onChange={(e) => setIsRest(e.target.checked)} data-testid="day-rest" />
          <span>День отдыха</span>
        </label>

        <div className="cfg-actions">
          <button className="cfg-btn-cancel" onClick={onClose}>Отмена</button>
          <button className="cfg-btn-save" onClick={submit} disabled={saving} data-testid="day-save">
            {saving ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
    </Portal>
  );
}

/* ---------- Главный редактор ---------- */
export default function CoachPlanEditor() {
  const { athleteId } = useParams();
  const aid = Number(athleteId);
  const { user } = useUser();
  const coachId = user?.telegram_id;
  const navigate = useNavigate();
  const location = useLocation();
  const requestedWeek = location.state?.week;  // открыть редактор сразу на этой неделе
  useBackButton(true, () => navigate(`/coach/${aid}`));

  const [athlete, setAthlete] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState(requestedWeek || 1);
  const [saving, setSaving] = useState(false);

  const [exModal, setExModal] = useState(null); // {week, day, order|null, data}
  const [dayModal, setDayModal] = useState(null); // {mode, week, initial}
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");

  const load = useCallback(async () => {
    if (!coachId || !aid) return;
    setLoading(true);
    try {
      const a = await getUserById(aid).catch(() => null);
      setAthlete(a);
      const p = await getCoachClientPlan(coachId, aid).catch((e) => {
        if (e?.response?.status === 403) toast.error("Нет доступа к этому спортсмену");
        return null;
      });
      setPlan(p);
      if (p) {
        const total = (p.weeks || []).length || 1;
        const want = requestedWeek || selectedWeek;
        setSelectedWeek(Math.min(Math.max(1, want), total));
      }
    } finally {
      setLoading(false);
    }
  }, [coachId, aid, requestedWeek]);

  useEffect(() => {
    load();
  }, [load]);

  const weeks = [...((plan && plan.weeks) || [])].sort((a, b) => (a.week_index || 0) - (b.week_index || 0));
  const weekObj = weeks.find((w) => w.week_index === selectedWeek) || weeks[0] || null;
  const days = [...((weekObj && weekObj.days) || [])].sort((a, b) => (a.day_index || 0) - (b.day_index || 0));
  const usedDays = days.map((d) => d.day_index);

  const run = async (fn, okMsg) => {
    setSaving(true);
    try {
      const updated = await fn();
      setPlan(updated);
      if (okMsg) toast.success(okMsg);
      hapticNotify("success");
      return updated;
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Не удалось сохранить");
      return null;
    } finally {
      setSaving(false);
    }
  };

  // --- meta
  const saveName = async () => {
    const nm = nameDraft.trim();
    if (!nm) { setRenaming(false); return; }
    await run(() => updatePlanMeta(plan.id, { name: nm }), "Название обновлено");
    setRenaming(false);
  };

  // --- weeks
  const onAddWeek = async () => {
    haptic("light");
    const updated = await run(() => addPlanWeek(plan.id), "Неделя добавлена");
    if (updated) setSelectedWeek((updated.weeks || []).length);
  };
  const onDeleteWeek = async () => {
    if (!weekObj) return;
    haptic("medium");
    const updated = await run(() => deletePlanWeek(plan.id, weekObj.week_index), "Неделя удалена");
    if (updated) setSelectedWeek((w) => Math.min(w, (updated.weeks || []).length || 1));
  };

  // --- days
  const saveDay = async (body) => {
    await run(
      () => upsertPlanDay(plan.id, { week: weekObj.week_index, day: body.day, title: body.title, is_rest: body.is_rest }),
      "День сохранён"
    );
    setDayModal(null);
  };
  const onDeleteDay = async (d) => {
    haptic("medium");
    await run(() => deletePlanDay(plan.id, weekObj.week_index, d.day_index), "День удалён");
  };

  // --- exercises
  const saveExercise = async (body) => {
    const payload = { ...body, week: exModal.week, day: exModal.day };
    if (exModal.order != null) payload.order = exModal.order;
    await run(() => upsertPlanExercise(plan.id, payload), "Упражнение сохранено");
    setExModal(null);
  };
  const onDeleteExercise = async (d, order) => {
    haptic("light");
    await run(() => deletePlanExercise(plan.id, weekObj.week_index, d.day_index, order), "Упражнение удалено");
  };

  const athleteName = athlete?.first_name || "Спортсмен";

  return (
    <div className="coach-page" data-testid="plan-editor-page">
      <header className="coach-header">
        <button className="coach-back" onClick={() => navigate(`/coach/${aid}`)} aria-label="Назад" data-testid="editor-back">
          <ArrowLeft size={22} />
        </button>
        <h1 className="coach-title">Редактор плана</h1>
      </header>

      {loading ? (
        <div className="coach-empty">Загрузка…</div>
      ) : !plan ? (
        <div className="coach-empty" data-testid="editor-noplan">
          У спортсмена нет плана. Сначала назначьте программу на его карточке.
        </div>
      ) : (
        <>
          {/* Имя плана */}
          <div className="ed-planhead">
            {renaming ? (
              <div className="ed-rename">
                <input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} data-testid="plan-name-input" autoFocus />
                <button className="ed-icon-ok" onClick={saveName} data-testid="plan-name-save"><Check size={18} /></button>
                <button className="ed-icon-x" onClick={() => setRenaming(false)}><X size={18} /></button>
              </div>
            ) : (
              <button className="ed-planname" onClick={() => { setNameDraft(plan.name || ""); setRenaming(true); }} data-testid="plan-name">
                {plan.name} <Pencil size={14} />
              </button>
            )}
            <div className="ed-plansub">{athleteName} · {weeks.length} нед.</div>
          </div>

          {/* Недели */}
          <div className="ed-weeks" data-testid="editor-weeks">
            {weeks.map((w) => (
              <button
                key={w.week_index}
                className={`ed-week-pill ${w.week_index === selectedWeek ? "active" : ""}`}
                onClick={() => setSelectedWeek(w.week_index)}
                data-testid={`week-pill-${w.week_index}`}
              >
                Нед. {w.week_index}
              </button>
            ))}
            <button className="ed-week-add" onClick={onAddWeek} disabled={saving} data-testid="add-week-btn" aria-label="Добавить неделю">
              <Plus size={16} />
            </button>
          </div>

          {weekObj ? (
            <>
              <div className="ed-week-actions">
                <span className="ed-week-label">Неделя {weekObj.week_index}</span>
                {weeks.length > 1 ? (
                  <button className="ed-del-week" onClick={onDeleteWeek} disabled={saving} data-testid="delete-week-btn">
                    <Trash2 size={14} /> Удалить неделю
                  </button>
                ) : null}
              </div>

              {/* Дни */}
              {days.length === 0 ? (
                <div className="coach-empty">В этой неделе нет дней. Добавьте день.</div>
              ) : (
                days.map((d) => (
                  <div className="ed-day" key={d.day_index} data-testid={`day-card-${d.day_index}`}>
                    <div className="ed-day-head">
                      <div className="ed-day-titles">
                        <span className="ed-day-name">{d.title || weekdayFull(d.day_index)}</span>
                        <span className="ed-day-sub">{weekdayFull(d.day_index)}{d.is_rest ? " · отдых" : ""}</span>
                      </div>
                      <div className="ed-day-acts">
                        <button className="ed-icon" onClick={() => setDayModal({ mode: "edit", initial: d })} aria-label="Изменить день" data-testid={`edit-day-${d.day_index}`}>
                          <Pencil size={15} />
                        </button>
                        <button className="ed-icon ed-icon-danger" onClick={() => onDeleteDay(d)} aria-label="Удалить день" data-testid={`delete-day-${d.day_index}`}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>

                    {!d.is_rest ? (
                      <>
                        <div className="ed-ex-list">
                          {(d.exercises || []).sort((a, b) => (a.order || 0) - (b.order || 0)).map((ex, i) => (
                            <div className="ed-ex-row" key={i} data-testid={`ex-row-${d.day_index}-${i}`}>
                              <div className="ed-ex-info">
                                <span className="ed-ex-name">{ex.exercise_name}</span>
                                <span className="ed-ex-sets">{fmtSets(ex)}</span>
                              </div>
                              <div className="ed-ex-acts">
                                <button className="ed-icon" onClick={() => setExModal({ week: weekObj.week_index, day: d.day_index, order: i, data: ex })} aria-label="Изменить" data-testid={`edit-ex-${d.day_index}-${i}`}>
                                  <Pencil size={14} />
                                </button>
                                <button className="ed-icon ed-icon-danger" onClick={() => onDeleteExercise(d, i)} aria-label="Удалить" data-testid={`delete-ex-${d.day_index}-${i}`}>
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          ))}
                          {(!d.exercises || d.exercises.length === 0) ? (
                            <div className="ed-ex-empty">Нет упражнений</div>
                          ) : null}
                        </div>
                        <button className="ed-add-ex" onClick={() => setExModal({ week: weekObj.week_index, day: d.day_index, order: null, data: null })} data-testid={`add-ex-${d.day_index}`}>
                          <Plus size={15} /> Упражнение
                        </button>
                      </>
                    ) : null}
                  </div>
                ))
              )}

              <button className="coach-primary-btn ed-add-day" onClick={() => setDayModal({ mode: "add", initial: null })} disabled={saving} data-testid="add-day-btn">
                <CalendarPlus size={16} /> Добавить день
              </button>
            </>
          ) : null}
        </>
      )}

      {exModal ? (
        <ExerciseModal
          initial={exModal.data}
          saving={saving}
          onClose={() => setExModal(null)}
          onSave={saveExercise}
        />
      ) : null}

      {dayModal ? (
        <DayModal
          mode={dayModal.mode}
          used={usedDays}
          initial={dayModal.initial}
          saving={saving}
          onClose={() => setDayModal(null)}
          onSave={saveDay}
        />
      ) : null}
    </div>
  );
}
