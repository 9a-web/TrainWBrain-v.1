import React, { useEffect, useState } from "react";
import {
  Check, X, Wand2, ChevronDown, CheckCircle2,
} from "lucide-react";
import "./WorkoutView.css";

// ---------- helpers ----------
export const fmtWeight = (w) => {
  if (w === null || w === undefined) return "";
  const n = Number(w);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
};

export const fmtDuration = (sec) => {
  const s = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h > 0 ? `${h}ч. ${m}м.` : `${m}м.`;
};

const STATUS_META = {
  done: { label: "Выполнено", color: "#3BD16F" },
  in_progress: { label: "В процессе", color: "#FFB020" },
  skipped: { label: "Пропущено", color: "#FF5A5A" },
  pending: { label: "Ожидает", color: "#8a8a8a" },
};

// ---------- декоративный мини-график «Прогноз на 4 недели» ----------
const FORECAST_PATHS = [
  "M0,46 C18,42 32,50 52,30 C72,12 92,28 118,12 C132,4 150,10 150,10",
  "M0,52 C24,50 44,48 68,42 C94,34 110,18 134,9 L150,7",
  "M0,40 C20,44 36,26 56,34 C78,42 96,20 120,16 C134,13 150,18 150,18",
];

const ForecastChart = ({ seed = 0 }) => {
  const d = FORECAST_PATHS[seed % FORECAST_PATHS.length];
  const gid = `fc-${seed}`;
  return (
    <svg viewBox="0 0 150 60" className="forecast-svg" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FF8A24" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#FF8A24" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${d} L150,60 L0,60 Z`} fill={`url(#${gid})`} />
      <path d={d} fill="none" stroke="#FF8A24" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
};

// ---------- карточка упражнения ----------
const ExerciseCard = ({ ex, isPreview, onAction, onEdit }) => {
  const meta = STATUS_META[ex.status] || STATUS_META.pending;
  const isActive = !isPreview && ex.status === "in_progress";
  const isFinishedCard = !isPreview && (ex.status === "done" || ex.status === "skipped");

  const defaultOpen = isPreview || ex.status === "in_progress" || ex.status === "pending";
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`ex-card ${isActive ? "ex-card-active" : ""}`} data-testid={`exercise-card-${ex.order}`}>
      <button type="button" className="ex-head" onClick={() => setOpen((o) => !o)}>
        <div className="ex-head-left">
          <span className="ex-name">{ex.exercise_name}</span>
          {!isPreview ? (
            <span className="ex-status" style={{ color: meta.color }}>
              ● {meta.label}
            </span>
          ) : (
            ex.difficulty ? <span className="ex-status ex-status-plan">● {ex.difficulty}</span> : null
          )}
        </div>
        <div className="ex-head-right">
          {isActive ? (
            <>
              <span
                className="ex-btn ex-btn-done"
                role="button"
                tabIndex={0}
                data-testid={`done-${ex.order}`}
                onClick={(e) => { e.stopPropagation(); onAction(ex.order, "done"); }}
              >
                <Check size={16} strokeWidth={3} /> Выполнить
              </span>
              <span
                className="ex-btn ex-btn-magic"
                role="button"
                tabIndex={0}
                data-testid={`edit-${ex.order}`}
                onClick={(e) => { e.stopPropagation(); onEdit(ex); }}
              >
                <Wand2 size={15} />
              </span>
              <span
                className="ex-btn ex-btn-skip"
                role="button"
                tabIndex={0}
                data-testid={`skip-${ex.order}`}
                onClick={(e) => { e.stopPropagation(); onAction(ex.order, "skip"); }}
              >
                <X size={16} strokeWidth={3} />
              </span>
            </>
          ) : isFinishedCard ? (
            <span
              className="ex-btn ex-btn-magic-sm"
              role="button"
              tabIndex={0}
              data-testid={`edit-${ex.order}`}
              onClick={(e) => { e.stopPropagation(); onEdit(ex); }}
            >
              <Wand2 size={14} />
            </span>
          ) : null}
          <ChevronDown size={22} className={`ex-chevron ${open ? "open" : ""}`} />
        </div>
      </button>

      {open ? (
        <div className="ex-body">
          <div className="ex-plan">
            <div className="ex-plan-label">План:</div>
            {(ex.sets_scheme || []).map((s, i) => (
              <div className="ex-plan-row" key={i}>
                {s.weight !== null && s.weight !== undefined ? (
                  <span className="ex-plan-weight">{fmtWeight(s.weight)}кг</span>
                ) : (
                  <span className="ex-plan-weight ex-plan-bw">Свой вес</span>
                )}
                <span className="ex-plan-dash">—</span>
                <span className="ex-plan-scheme">{s.sets}×{s.reps}</span>
                {s.percent_1rm !== null && s.percent_1rm !== undefined ? (
                  <>
                    <span className="ex-plan-bar" />
                    <span className="ex-plan-pct">{s.percent_1rm}%</span>
                  </>
                ) : null}
              </div>
            ))}
            <div className="ex-meta">
              <div className="ex-meta-row">Тоннаж: <b>{ex.tonnage}кг</b></div>
              {ex.muscle_letter ? <div className="ex-meta-row">Группа: <b>{ex.muscle_letter}</b></div> : null}
              {ex.difficulty ? <div className="ex-meta-row">Сложность: <b>{ex.difficulty}</b></div> : null}
            </div>
          </div>
          <div className="ex-forecast">
            <ForecastChart seed={ex.order} />
            <span className="ex-forecast-caption">Прогноз на 4 недели</span>
          </div>
        </div>
      ) : null}
    </div>
  );
};

// ---------- модалка редактирования упражнения (✨) ----------
const EditExerciseModal = ({ ex, onClose, onSave }) => {
  const [name, setName] = useState(ex.exercise_name);
  const [sets, setSets] = useState(
    (ex.sets_scheme || []).map((s) => ({
      weight: s.weight ?? "",
      sets: s.sets ?? 1,
      reps: s.reps ?? 1,
    }))
  );

  const updateSet = (i, field, value) => {
    setSets((prev) => prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)));
  };

  const handleSave = () => {
    const sets_scheme = sets.map((s) => ({
      weight: s.weight === "" || s.weight === null ? null : Number(s.weight),
      sets: Number(s.sets) || 1,
      reps: Number(s.reps) || 1,
    }));
    onSave(ex.order, { exercise_name: name, sets_scheme });
  };

  return (
    <div className="edit-overlay" onClick={onClose} data-testid="edit-modal">
      <div className="edit-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="edit-title">Изменить упражнение</h3>
        <label className="edit-label">Название</label>
        <input className="edit-input" value={name} onChange={(e) => setName(e.target.value)} />
        <div className="edit-sets">
          <div className="edit-sets-head">
            <span>Вес, кг</span><span>Подходы</span><span>Повторы</span>
          </div>
          {sets.map((s, i) => (
            <div className="edit-set-row" key={i}>
              <input className="edit-input-sm" type="number" value={s.weight}
                onChange={(e) => updateSet(i, "weight", e.target.value)} placeholder="—" />
              <input className="edit-input-sm" type="number" value={s.sets}
                onChange={(e) => updateSet(i, "sets", e.target.value)} />
              <input className="edit-input-sm" type="number" value={s.reps}
                onChange={(e) => updateSet(i, "reps", e.target.value)} />
            </div>
          ))}
        </div>
        <div className="edit-actions">
          <button className="edit-btn-cancel" onClick={onClose}>Отмена</button>
          <button className="edit-btn-save" onClick={handleSave} data-testid="edit-save">Сохранить</button>
        </div>
      </div>
    </div>
  );
};

// ---------- основной вид тренировки ----------
const WorkoutView = ({ view, isPreview = false, paused = false, onAction, onEditSave }) => {
  const [now, setNow] = useState(() => Date.now());
  const [editing, setEditing] = useState(null);

  const status = view.status;
  const stats = view.stats || {};
  const exercises = view.exercises || [];

  // живой таймер во время тренировки
  useEffect(() => {
    if (status !== "in_progress" || paused) return undefined;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [status, paused]);

  const durationSec =
    status === "in_progress" && view.started_at && !paused
      ? Math.max(0, Math.floor((now - new Date(view.started_at).getTime()) / 1000))
      : stats.duration_sec || 0;

  const isFinished = status === "finished";

  const statusIcon = isFinished ? (
    <img src="/complete.svg" alt="Завершено" width={24} height={24} className="wv-status-img" />
  ) : (
    <img
      src="/run.svg"
      alt={status === "in_progress" ? "Тренировка идёт" : "Не начата"}
      width={24}
      height={24}
      className={`wv-status-img ${status === "in_progress" && !paused ? "wv-status-spin" : ""}`}
    />
  );

  const handleSave = (order, body) => {
    if (onEditSave) onEditSave(order, body);
    setEditing(null);
  };

  return (
    <div className="workout-view" data-testid="workout-view">
      {/* Статистика дня */}
      <div className="wv-stats" data-testid="workout-stats">
        <div className="wv-status-icon">{statusIcon}</div>
        <div className="wv-stat">
          <span className="wv-stat-val">{stats.tonnage || 0}кг</span>
          <span className="wv-stat-label">Тоннаж</span>
        </div>
        <div className="wv-stat">
          <span className="wv-stat-val">{stats.group || "—"}</span>
          <span className="wv-stat-label">Группа</span>
        </div>
        <div className="wv-stat">
          <span className="wv-stat-val">{stats.difficulty || "—"}</span>
          <span className="wv-stat-label">Сложность</span>
        </div>
        <div className="wv-stat">
          <span className="wv-stat-val">{fmtDuration(durationSec)}</span>
          <span className="wv-stat-label">Время</span>
        </div>
      </div>

      {/* Список упражнений */}
      <div className="wv-exercises" data-testid="day-exercises">
        {exercises.map((ex) => (
          <ExerciseCard
            key={ex.order}
            ex={ex}
            isPreview={isPreview}
            onAction={onAction}
            onEdit={(e) => setEditing(e)}
          />
        ))}
      </div>

      {/* Нижний прогресс-бар */}
      {!isPreview ? (
        <div className="wv-footer" data-testid="workout-footer">
          <div className="wv-footer-top">
            {isFinished ? <CheckCircle2 size={18} className="wv-footer-check" /> : null}
            <span className="wv-footer-count">
              {stats.done_count || 0}/{stats.total_count || 0} упражнений ({stats.progress_pct || 0}%)
            </span>
          </div>
          <div className="wv-segments">
            {exercises.map((ex) => (
              <span key={ex.order} className={`wv-seg wv-seg-${ex.status}`} />
            ))}
          </div>
          <div className="wv-footer-status">
            {isFinished ? "Тренировка закончилась" : "Тренировка идёт"}
          </div>
        </div>
      ) : null}

      {editing ? (
        <EditExerciseModal ex={editing} onClose={() => setEditing(null)} onSave={handleSave} />
      ) : null}
    </div>
  );
};

export default WorkoutView;
