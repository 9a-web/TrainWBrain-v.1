import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, Dumbbell, Check, RefreshCw, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@/context/UserContext";
import {
  getCoachClientPlan, getUserById, getTemplates, createPlan,
  setPlanVisibility, publishPlanWeek, setPlanTrainingDays,
} from "@/api";
import { haptic, hapticNotify } from "@/lib/platform";
import { useBackButton } from "@/hooks/useTelegramUI";
import "./Coach.css";

const WEEKDAYS = [
  { idx: 1, label: "Пн" }, { idx: 2, label: "Вт" }, { idx: 3, label: "Ср" },
  { idx: 4, label: "Чт" }, { idx: 5, label: "Пт" }, { idx: 6, label: "Сб" }, { idx: 7, label: "Вс" },
];

// Модалка настройки шаблона (максимумы + дни) — для шаблонов с requires_maxes
function AssignModal({ tpl, onClose, onSubmit, submitting }) {
  const needMaxes = !!tpl.requires_maxes;
  const daysNeeded = tpl.days_per_week || 3;
  const [squat, setSquat] = useState("");
  const [bench, setBench] = useState("");
  const [deadlift, setDeadlift] = useState("");
  const [days, setDays] = useState([]);

  const toggleDay = (idx) =>
    setDays((prev) =>
      prev.includes(idx)
        ? prev.filter((d) => d !== idx)
        : prev.length >= daysNeeded ? prev : [...prev, idx]
    );

  const maxesOk = !needMaxes || (Number(squat) > 0 && Number(bench) > 0 && Number(deadlift) > 0);
  const daysOk = days.length === daysNeeded;
  const canSubmit = maxesOk && daysOk && !submitting;

  const submit = () => {
    if (!canSubmit) return;
    const payload = { training_days: [...days].sort((a, b) => a - b) };
    if (needMaxes) payload.maxes = { squat: Number(squat), bench: Number(bench), deadlift: Number(deadlift) };
    onSubmit(payload);
  };

  return (
    <div className="cfg-overlay" onClick={onClose} data-testid="assign-config-modal">
      <div className="cfg-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="cfg-title">{tpl.name}</h3>
        <p className="cfg-sub">Настройте программу под спортсмена</p>
        {needMaxes ? (
          <div className="cfg-section">
            <div className="cfg-section-title">Максимумы спортсмена (1ПМ), кг</div>
            <div className="cfg-maxes">
              <label className="cfg-max"><span>Присед</span>
                <input type="number" inputMode="decimal" value={squat} onChange={(e) => setSquat(e.target.value)} placeholder="0" /></label>
              <label className="cfg-max"><span>Жим</span>
                <input type="number" inputMode="decimal" value={bench} onChange={(e) => setBench(e.target.value)} placeholder="0" /></label>
              <label className="cfg-max"><span>Тяга</span>
                <input type="number" inputMode="decimal" value={deadlift} onChange={(e) => setDeadlift(e.target.value)} placeholder="0" /></label>
            </div>
          </div>
        ) : null}
        <div className="cfg-section">
          <div className="cfg-section-title">Дни тренировок <span className="cfg-hint">выберите {daysNeeded}</span></div>
          <div className="cfg-days">
            {WEEKDAYS.map((d) => (
              <button key={d.idx} type="button" className={`cfg-day ${days.includes(d.idx) ? "active" : ""}`} onClick={() => toggleDay(d.idx)}>
                {d.label}
              </button>
            ))}
          </div>
        </div>
        <div className="cfg-actions">
          <button className="cfg-btn-cancel" onClick={onClose}>Отмена</button>
          <button className="cfg-btn-save" onClick={submit} disabled={!canSubmit} data-testid="assign-submit">
            {submitting ? "Назначаем…" : "Назначить"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CoachClient() {
  const { athleteId } = useParams();
  const aid = Number(athleteId);
  const { user } = useUser();
  const coachId = user?.telegram_id;
  const navigate = useNavigate();
  useBackButton(true, () => navigate("/coach"));

  const [athlete, setAthlete] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState([]);
  const [picking, setPicking] = useState(false);
  const [assignTpl, setAssignTpl] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadPlan = useCallback(async () => {
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
    } finally {
      setLoading(false);
    }
  }, [coachId, aid]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  const openPicker = async () => {
    haptic("light");
    setPicking(true);
    if (templates.length === 0) {
      try {
        setTemplates(await getTemplates());
      } catch (e) {
        /* no-op */
      }
    }
  };

  const assign = async (tpl, extra = {}) => {
    setBusy(true);
    try {
      const p = await createPlan({
        athlete_telegram_id: aid,
        template_id: tpl.id,
        coach_telegram_id: coachId,
        ...extra,
      });
      setPlan(p);
      setAssignTpl(null);
      setPicking(false);
      hapticNotify("success");
      toast.success("Программа назначена как черновик");
    } catch (e) {
      toast.error("Не удалось назначить программу");
    } finally {
      setBusy(false);
    }
  };

  const handleChoose = (tpl) => {
    if (tpl.requires_maxes) setAssignTpl(tpl);
    else assign(tpl);
  };

  const toggleVisibility = async () => {
    if (!plan) return;
    haptic("medium");
    const next = plan.visibility === "published" ? "draft" : "published";
    setBusy(true);
    try {
      const p = await setPlanVisibility(plan.id, next);
      setPlan(p);
      hapticNotify("success");
      toast.success(next === "published" ? "План опубликован — спортсмен его видит" : "План скрыт (черновик)");
    } catch (e) {
      toast.error("Не удалось изменить видимость");
    } finally {
      setBusy(false);
    }
  };

  const toggleDay = async (idx) => {
    if (!plan) return;
    haptic("light");
    const cur = new Set(plan.training_days || []);
    if (cur.has(idx)) cur.delete(idx);
    else cur.add(idx);
    const arr = [...cur].sort((a, b) => a - b);
    setPlan({ ...plan, training_days: arr });
    try {
      const p = await setPlanTrainingDays(plan.id, arr);
      setPlan(p);
    } catch (e) {
      toast.error("Не удалось сохранить дни");
      loadPlan();
    }
  };

  const toggleWeek = async (wk) => {
    if (!plan) return;
    haptic("light");
    const next = !(wk.published !== false);
    try {
      const p = await publishPlanWeek(plan.id, wk.week_index, next);
      setPlan(p);
    } catch (e) {
      toast.error("Не удалось изменить неделю");
    }
  };

  const athleteName = athlete?.first_name || "Спортсмен";
  const isPublished = plan?.visibility === "published";

  return (
    <div className="coach-page" data-testid="coach-client-page">
      <header className="coach-header">
        <button className="coach-back" onClick={() => navigate("/coach")} aria-label="Назад" data-testid="coach-client-back">
          <ArrowLeft size={22} />
        </button>
        <h1 className="coach-title">{athleteName}</h1>
      </header>

      {loading ? (
        <div className="coach-empty">Загрузка…</div>
      ) : !plan ? (
        <>
          <div className="coach-noplan" data-testid="client-noplan-block">
            <Dumbbell size={26} />
            <p>У спортсмена нет активной программы.</p>
            {!picking ? (
              <button className="coach-primary-btn" onClick={openPicker} data-testid="assign-program-btn">
                Назначить программу
              </button>
            ) : null}
          </div>
          {picking ? (
            <div className="programs-list" data-testid="assign-template-list">
              {templates.map((tpl) => (
                <div className="program-card" key={tpl.id}>
                  <div className="program-card-head">
                    <div className="program-card-icon"><Dumbbell size={20} /></div>
                    <div className="program-card-titles">
                      <h3 className="program-card-name">{tpl.name}</h3>
                    </div>
                  </div>
                  <p className="program-card-desc">{tpl.description}</p>
                  <div className="program-card-meta">
                    <span>{tpl.weeks_count} нед.</span><span>·</span><span>{tpl.days_per_week} дн./нед.</span>
                  </div>
                  <button className="program-card-button" onClick={() => handleChoose(tpl)} disabled={busy} data-testid={`assign-choose-${tpl.slug || tpl.id}`}>
                    {busy ? "Назначаем…" : "Назначить"}
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <>
          {/* Видимость плана */}
          <div className="coach-block" data-testid="visibility-block">
            <div className="coach-block-head">
              <div>
                <div className="coach-block-title">{plan.name}</div>
                <div className="coach-block-sub">
                  {plan.weeks?.length || 0} нед. · {isPublished ? "виден спортсмену" : "черновик (скрыт)"}
                </div>
              </div>
              <span className={`vis-badge vis-${plan.visibility}`}>
                {isPublished ? "опубликован" : "черновик"}
              </span>
            </div>
            <button
              className={`coach-primary-btn ${isPublished ? "is-secondary" : ""}`}
              onClick={toggleVisibility}
              disabled={busy}
              data-testid="toggle-visibility-btn"
            >
              {isPublished ? (<><EyeOff size={16} /> Скрыть (вернуть в черновик)</>) : (<><Eye size={16} /> Опубликовать для спортсмена</>)}
            </button>
          </div>

          {/* Тренировочные дни */}
          <div className="coach-block" data-testid="training-days-block">
            <div className="coach-block-title">Тренировочные дни</div>
            <div className="coach-block-sub">Спортсмен увидит их в недельном календаре</div>
            <div className="cfg-days">
              {WEEKDAYS.map((d) => (
                <button
                  key={d.idx}
                  type="button"
                  className={`cfg-day ${(plan.training_days || []).includes(d.idx) ? "active" : ""}`}
                  onClick={() => toggleDay(d.idx)}
                  data-testid={`coach-day-${d.idx}`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Недели плана */}
          <div className="coach-block" data-testid="weeks-block">
            <div className="coach-block-title">Недели плана</div>
            <div className="coach-block-sub">Открывайте недели спортсмену по одной</div>
            <div className="weeks-list">
              {[...(plan.weeks || [])]
                .sort((a, b) => (a.week_index || 0) - (b.week_index || 0))
                .map((wk) => {
                  const wkPublished = wk.published !== false;
                  const workoutDays = (wk.days || []).filter((d) => !d.is_rest).length;
                  return (
                    <div className="week-row" key={wk.week_index} data-testid={`week-row-${wk.week_index}`}>
                      <div className="week-info">
                        <span className="week-name">Неделя {wk.week_index}</span>
                        <span className="week-days">{workoutDays} трен.</span>
                      </div>
                      <button
                        className={`week-toggle ${wkPublished ? "on" : "off"}`}
                        onClick={() => toggleWeek(wk)}
                        data-testid={`week-toggle-${wk.week_index}`}
                        aria-pressed={wkPublished}
                      >
                        {wkPublished ? (<><Eye size={14} /> видна</>) : (<><EyeOff size={14} /> скрыта</>)}
                      </button>
                    </div>
                  );
                })}
            </div>
          </div>

          <button
            className="coach-primary-btn is-secondary ed-open-btn"
            onClick={() => navigate(`/coach/${aid}/edit`)}
            data-testid="edit-plan-btn"
          >
            <Pencil size={16} /> Редактировать план
          </button>

          <button className="coach-text-btn" onClick={openPicker} data-testid="reassign-btn">
            <RefreshCw size={14} /> Сменить программу
          </button>
          {picking ? (
            <div className="programs-list" data-testid="reassign-template-list">
              {templates.map((tpl) => (
                <div className="program-card" key={tpl.id}>
                  <div className="program-card-head">
                    <div className="program-card-icon"><Dumbbell size={20} /></div>
                    <div className="program-card-titles">
                      <h3 className="program-card-name">{tpl.name}</h3>
                    </div>
                  </div>
                  <div className="program-card-meta">
                    <span>{tpl.weeks_count} нед.</span><span>·</span><span>{tpl.days_per_week} дн./нед.</span>
                  </div>
                  <button className="program-card-button" onClick={() => handleChoose(tpl)} disabled={busy} data-testid={`reassign-choose-${tpl.slug || tpl.id}`}>
                    {busy ? "Назначаем…" : "Назначить"}
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </>
      )}

      {assignTpl ? (
        <AssignModal
          tpl={assignTpl}
          submitting={busy}
          onClose={() => setAssignTpl(null)}
          onSubmit={(payload) => assign(assignTpl, payload)}
        />
      ) : null}
    </div>
  );
}
