import React, { useEffect, useState } from "react";
import {
  Check, X, WandSparkles, ChevronDown, CheckCircle2, Trash2, Plus, MessageSquareText, Pencil, Layers,
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

// Дифф подходов сессии относительно плана: normal | edited (добавлен/изменён) | deleted (удалён из плана)
const setKey = (s) => `${s.weight === null || s.weight === undefined ? "bw" : s.weight}|${s.sets}|${s.reps}`;

const diffSets = (cur, plan) => {
  const c = cur || [];
  const p = plan || [];
  if (!p.length) return c.map((s) => ({ ...s, _state: "normal" }));
  const planCount = {};
  p.forEach((s) => { const k = setKey(s); planCount[k] = (planCount[k] || 0) + 1; });
  const rows = [];
  c.forEach((s) => {
    const k = setKey(s);
    if (planCount[k] > 0) { planCount[k] -= 1; rows.push({ ...s, _state: "normal" }); }
    else rows.push({ ...s, _state: "edited" });
  });
  p.forEach((s) => {
    const k = setKey(s);
    if (planCount[k] > 0) { planCount[k] -= 1; rows.push({ ...s, _state: "deleted" }); }
  });
  return rows;
};

const STATUS_META = {
  done: { label: "Выполнено", color: "#3BD16F" },
  in_progress: { label: "В процессе", color: "#FFB020" },
  skipped: { label: "Пропущено", color: "#FF5A5A" },
  pending: { label: "Ожидает", color: "#FFC83F" },
};

// ---------- мини-график: динамика топового веса упражнения по неделям плана ----------
const ForecastChart = ({ series, currentWeek }) => {
  if (!series || series.length < 2) return null;
  const W = 150;
  const H = 56;
  const pad = 8;
  const vals = series.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const n = series.length;
  const xx = (i) => pad + (i / (n - 1)) * (W - 2 * pad);
  const yy = (v) => (H - pad) - ((v - min) / range) * (H - 2 * pad);
  const pts = series.map((p, i) => [xx(i), yy(p.value)]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${pts[n - 1][0].toFixed(1)},${H} L${pts[0][0].toFixed(1)},${H} Z`;
  const curIdx = series.findIndex((p) => p.week === currentWeek);
  const gid = `fc-${n}-${Math.round(min)}-${Math.round(max)}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="forecast-svg" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FF8A24" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#FF8A24" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke="#FF8A24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {curIdx >= 0 ? (
        <circle cx={pts[curIdx][0]} cy={pts[curIdx][1]} r="3.6" fill="#FFDA24" stroke="#1c1c1c" strokeWidth="1.5" />
      ) : null}
    </svg>
  );
};

// ---------- карточка упражнения ----------
const ExerciseCard = ({ ex, isPreview, onAction, onEdit, forecast, currentWeek }) => {
  const meta = STATUS_META[ex.status] || STATUS_META.pending;
  const isActive = !isPreview && ex.status === "in_progress";
  const isFinishedCard = !isPreview && (ex.status === "done" || ex.status === "skipped");
  const isAcc = !!ex.is_accessory;

  // По умолчанию карточки свёрнуты
  const [open, setOpen] = useState(false);

  // Кнопки действий: у основных — только у активного; у подсобных — пока не выполнено
  const showActions = isActive || (isAcc && !isPreview && ex.status === "pending");

  return (
    <div className={`ex-card ${isActive ? "ex-card-active" : ""}`} data-testid={`exercise-card-${ex.order}`}>
      <button type="button" className="ex-head" onClick={() => setOpen((o) => !o)}>
        <div className="ex-head-left">
          <span className="ex-name">{ex.exercise_name}</span>
          <span className="ex-status-line">
            <span className="ex-status" style={{ color: meta.color }}>
              ● {meta.label}
            </span>
            {ex.edited ? (
              <span className="ex-edited-flag" title="Упражнение изменено" data-testid={`edited-flag-${ex.order}`}>
                <Pencil size={12} />
              </span>
            ) : null}
            {ex.comment ? (
              <span className="ex-comment-flag" title="Есть комментарий тренеру" data-testid={`comment-flag-${ex.order}`}>
                <MessageSquareText size={12} />
              </span>
            ) : null}
          </span>
        </div>
        <div className="ex-head-right">
          {isFinishedCard ? (
            <span
              className="ex-btn ex-btn-magic-sm"
              role="button"
              tabIndex={0}
              data-testid={`edit-${ex.order}`}
              onClick={(e) => { e.stopPropagation(); onEdit(ex); }}
            >
              <WandSparkles size={14} />
            </span>
          ) : null}
          <ChevronDown size={22} className={`ex-chevron ${open ? "open" : ""}`} />
        </div>
      </button>

      {showActions ? (
        <div className="ex-actions" data-testid={`actions-${ex.order}`}>
          <span
            className="ex-btn ex-btn-done"
            role="button"
            tabIndex={0}
            data-testid={`done-${ex.order}`}
            onClick={() => onAction(ex.order, "done")}
          >
            <Check size={16} strokeWidth={3} /> Выполнить
          </span>
          <span
            className="ex-btn ex-btn-magic"
            role="button"
            tabIndex={0}
            data-testid={`edit-${ex.order}`}
            onClick={() => onEdit(ex)}
          >
            <WandSparkles size={16} />
          </span>
          <span
            className="ex-btn ex-btn-skip"
            role="button"
            tabIndex={0}
            data-testid={`skip-${ex.order}`}
            onClick={() => onAction(ex.order, "skip")}
          >
            <X size={16} strokeWidth={3} />
          </span>
        </div>
      ) : null}

      {open ? (
        <>
          {isAcc ? (
            <div className="ex-acc-body">
              <div className="ex-acc-rec"><b>4 подхода</b></div>
            </div>
          ) : (
          <div className="ex-body">
            <div className="ex-plan">
              <div className="ex-plan-label">План:</div>
              {diffSets(ex.sets_scheme, ex.plan_sets_scheme).map((s, i) => (
                <div className={`ex-plan-row ${s._state === "deleted" ? "ex-plan-deleted" : ""}`} key={i}>
                  {s.weight !== null && s.weight !== undefined ? (
                    <span className="ex-plan-weight">{fmtWeight(s.weight)}кг</span>
                  ) : (
                    <span className="ex-plan-weight ex-plan-bw">Свой вес</span>
                  )}
                  <span className="ex-plan-dash">—</span>
                  <span className="ex-plan-scheme">{s.sets}×{s.reps}</span>
                  {s.percent_1rm !== null && s.percent_1rm !== undefined ? (
                    <span className="ex-plan-pctwrap">
                      <span className="ex-plan-bar" />
                      <span className="ex-plan-pct">{s.percent_1rm}%</span>
                    </span>
                  ) : (
                    <span />
                  )}
                  {s._state === "edited" ? (
                    <Pencil size={12} className="ex-plan-edit-ico" aria-label="изменён" />
                  ) : null}
                </div>
              ))}
              <div className="ex-meta">
                <div className="ex-meta-row">Тоннаж: <b>{ex.tonnage}кг</b></div>
                {ex.muscle_letter ? <div className="ex-meta-row">Группа: <b>{ex.muscle_letter}</b></div> : null}
                {ex.difficulty ? <div className="ex-meta-row">Сложность: <b>{ex.difficulty}</b></div> : null}
              </div>
            </div>
            {forecast && forecast.length >= 2 ? (
              <div className="ex-forecast">
                <ForecastChart series={forecast} currentWeek={currentWeek} />
                <span className="ex-forecast-caption">Вес по неделям</span>
              </div>
            ) : null}
          </div>
          )}
          {ex.comment ? (
            <div className="ex-comment" data-testid={`comment-${ex.order}`}>
              <div className="ex-comment-head">
                <MessageSquareText size={14} />
                <span>Заметки</span>
              </div>
              <p className="ex-comment-text">{ex.comment}</p>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
};

// ---------- модалка редактирования упражнения (✨) ----------
const COMMENT_MAX = 500;

const EditExerciseModal = ({ ex, onClose, onSave }) => {
  const [name, setName] = useState(ex.exercise_name);
  const [sets, setSets] = useState(
    (ex.sets_scheme || []).map((s) => ({
      weight: s.weight ?? "",
      sets: s.sets ?? 1,
      reps: s.reps ?? 1,
    }))
  );
  const [comment, setComment] = useState(ex.comment ?? "");

  const updateSet = (i, field, value) => {
    setSets((prev) => prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)));
  };

  const addSet = () => {
    setSets((prev) => {
      const last = prev[prev.length - 1];
      const base = last
        ? { weight: last.weight, sets: last.sets, reps: last.reps }
        : { weight: "", sets: 1, reps: 1 };
      return [...prev, base];
    });
  };

  const removeSet = (i) => {
    setSets((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)));
  };

  const handleSave = () => {
    const sets_scheme = sets.map((s) => ({
      weight: s.weight === "" || s.weight === null ? null : Number(s.weight),
      sets: Number(s.sets) || 1,
      reps: Number(s.reps) || 1,
    }));
    const trimmed = (comment || "").trim();
    onSave(ex.order, {
      exercise_name: name,
      sets_scheme,
      comment: trimmed ? trimmed.slice(0, COMMENT_MAX) : null,
    });
  };

  return (
    <div className="edit-overlay" onClick={onClose} data-testid="edit-modal">
      <div className="edit-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="edit-title">Изменить упражнение</h3>
        <label className="edit-label">Название</label>
        <input className="edit-input" value={name} onChange={(e) => setName(e.target.value)} />

        <div className="edit-sets">
          <div className="edit-sets-head">
            <span>Вес, кг</span><span>Подходы</span><span>Повторы</span><span aria-hidden="true" />
          </div>
          {sets.map((s, i) => (
            <div className="edit-set-row" key={i}>
              <input className="edit-input-sm" type="number" inputMode="decimal" value={s.weight}
                onChange={(e) => updateSet(i, "weight", e.target.value)} placeholder="—" />
              <input className="edit-input-sm" type="number" inputMode="numeric" value={s.sets}
                onChange={(e) => updateSet(i, "sets", e.target.value)} />
              <input className="edit-input-sm" type="number" inputMode="numeric" value={s.reps}
                onChange={(e) => updateSet(i, "reps", e.target.value)} />
              <button
                type="button"
                className="edit-set-del"
                data-testid={`edit-del-set-${i}`}
                disabled={sets.length <= 1}
                onClick={() => removeSet(i)}
                aria-label="Удалить подход"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          <button type="button" className="edit-add-set" onClick={addSet} data-testid="edit-add-set">
            <Plus size={16} /> Добавить подход
          </button>
        </div>

        <div className="edit-comment-block">
          <label className="edit-label edit-comment-label" htmlFor="edit-comment-field">
            <MessageSquareText size={15} /> Заметки
          </label>
          <textarea
            id="edit-comment-field"
            className="edit-textarea"
            data-testid="edit-comment"
            value={comment}
            maxLength={COMMENT_MAX}
            rows={3}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Например: последняя серия далась тяжело, потягивало плечо…"
          />
          <div className="edit-comment-foot">
            <span className="edit-comment-hint">
              <Check size={12} strokeWidth={3} /> Виден вашему тренеру
            </span>
            <span className="edit-comment-count">{(comment || "").length}/{COMMENT_MAX}</span>
          </div>
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
const WorkoutView = ({ view, isPreview = false, paused = false, onAction, onEditSave, forecastBySlug = {}, currentWeek }) => {
  const [now, setNow] = useState(() => Date.now());
  const [editing, setEditing] = useState(null);
  const [accOpen, setAccOpen] = useState(false);

  const status = view.status;
  const stats = view.stats || {};
  const exercises = view.exercises || [];
  const mainExs = exercises.filter((e) => !e.is_accessory);
  const accExs = exercises.filter((e) => e.is_accessory);

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

      {/* Список основных упражнений */}
      <div className="wv-exercises" data-testid="day-exercises">
        {mainExs.map((ex) => (
          <ExerciseCard
            key={ex.order}
            ex={ex}
            isPreview={isPreview}
            onAction={onAction}
            onEdit={(e) => setEditing(e)}
            forecast={forecastBySlug[ex.exercise_slug]}
            currentWeek={currentWeek}
          />
        ))}
      </div>

      {/* Папка подсобных упражнений */}
      {accExs.length > 0 ? (
        <div className="wv-accessory" data-testid="accessory-folder">
          <button
            type="button"
            className={`wv-accessory-head ${accOpen ? "open" : ""}`}
            onClick={() => setAccOpen((o) => !o)}
            data-testid="accessory-toggle"
          >
            <span className="wv-accessory-title">
              <Layers size={17} className="wv-accessory-ico" />
              Подсобные упражнения
              <span className="wv-accessory-count">{accExs.length}</span>
            </span>
            <ChevronDown size={20} className={`wv-accessory-chevron ${accOpen ? "open" : ""}`} />
          </button>
          {accOpen ? (
            <div className="wv-accessory-list" data-testid="accessory-list">
              {accExs.map((ex) => (
                <ExerciseCard
                  key={ex.order}
                  ex={ex}
                  isPreview={isPreview}
                  onAction={onAction}
                  onEdit={(e) => setEditing(e)}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

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
