import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Check, Dumbbell, Upload, PencilLine } from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@/context/UserContext";
import { getTemplates, getActivePlan, createPlan } from "@/api";
import "./Programs.css";

const LEVEL_LABELS = {
  beginner: "Новичок",
  intermediate: "Средний",
  advanced: "Продвинутый",
};
const GOAL_LABELS = {
  strength: "Сила",
  hypertrophy: "Масса",
  powerlifting: "Пауэрлифтинг",
  general: "Общее",
};

const WEEKDAYS = [
  { idx: 1, label: "Пн" }, { idx: 2, label: "Вт" }, { idx: 3, label: "Ср" },
  { idx: 4, label: "Чт" }, { idx: 5, label: "Пт" }, { idx: 6, label: "Сб" }, { idx: 7, label: "Вс" },
];

// Модалка настройки программы перед выбором: максимумы (1ПМ) + дни тренировок
const ProgramConfigModal = ({ tpl, onClose, onSubmit, submitting }) => {
  const needMaxes = !!tpl.requires_maxes;
  const daysNeeded = tpl.days_per_week || 3;
  const [squat, setSquat] = useState("");
  const [bench, setBench] = useState("");
  const [deadlift, setDeadlift] = useState("");
  const [days, setDays] = useState([]);

  const toggleDay = (idx) => {
    setDays((prev) =>
      prev.includes(idx)
        ? prev.filter((d) => d !== idx)
        : prev.length >= daysNeeded
          ? prev
          : [...prev, idx]
    );
  };

  const maxesOk = !needMaxes || (Number(squat) > 0 && Number(bench) > 0 && Number(deadlift) > 0);
  const daysOk = days.length === daysNeeded;
  const canSubmit = maxesOk && daysOk && !submitting;

  const submit = () => {
    if (!canSubmit) return;
    const payload = { training_days: [...days].sort((a, b) => a - b) };
    if (needMaxes) {
      payload.maxes = { squat: Number(squat), bench: Number(bench), deadlift: Number(deadlift) };
    }
    onSubmit(payload);
  };

  return (
    <div className="cfg-overlay" onClick={onClose} data-testid="program-config-modal">
      <div className="cfg-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="cfg-title">{tpl.name}</h3>
        <p className="cfg-sub">Настройте программу под себя</p>

        {needMaxes ? (
          <div className="cfg-section">
            <div className="cfg-section-title">Ваши максимумы (1ПМ), кг</div>
            <div className="cfg-maxes">
              <label className="cfg-max">
                <span>Присед</span>
                <input type="number" inputMode="decimal" value={squat}
                  onChange={(e) => setSquat(e.target.value)} placeholder="0" data-testid="max-squat" />
              </label>
              <label className="cfg-max">
                <span>Жим</span>
                <input type="number" inputMode="decimal" value={bench}
                  onChange={(e) => setBench(e.target.value)} placeholder="0" data-testid="max-bench" />
              </label>
              <label className="cfg-max">
                <span>Тяга</span>
                <input type="number" inputMode="decimal" value={deadlift}
                  onChange={(e) => setDeadlift(e.target.value)} placeholder="0" data-testid="max-deadlift" />
              </label>
            </div>
          </div>
        ) : null}

        <div className="cfg-section">
          <div className="cfg-section-title">
            Когда тренируетесь? <span className="cfg-hint">выберите {daysNeeded}</span>
          </div>
          <div className="cfg-days">
            {WEEKDAYS.map((d) => (
              <button
                key={d.idx}
                type="button"
                className={`cfg-day ${days.includes(d.idx) ? "active" : ""}`}
                onClick={() => toggleDay(d.idx)}
                data-testid={`day-${d.idx}`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        <div className="cfg-actions">
          <button className="cfg-btn-cancel" onClick={onClose}>Отмена</button>
          <button className="cfg-btn-save" onClick={submit} disabled={!canSubmit} data-testid="config-submit">
            {submitting ? "Назначаем…" : "Выбрать программу"}
          </button>
        </div>
      </div>
    </div>
  );
};

const Programs = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activePlan, setActivePlan] = useState(null);
  const [assigningId, setAssigningId] = useState(null);
  const [configTpl, setConfigTpl] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const d = await getTemplates();
        if (!cancelled) setTemplates(d);
      } catch (e) {
        if (!cancelled) setTemplates([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!user?.telegram_id) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const p = await getActivePlan(user.telegram_id);
        if (!cancelled) setActivePlan(p);
      } catch (e) {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.telegram_id]);

  const assign = async (tpl, extra = {}) => {
    setAssigningId(tpl.id);
    try {
      const plan = await createPlan({
        athlete_telegram_id: user.telegram_id,
        template_id: tpl.id,
        ...extra,
      });
      setActivePlan(plan);
      setConfigTpl(null);
      toast.success(`Программа «${tpl.name}» выбрана`);
      setTimeout(() => navigate("/"), 600);
    } catch (e) {
      toast.error("Не удалось выбрать программу");
    } finally {
      setAssigningId(null);
    }
  };

  const handleChoose = (tpl) => {
    if (!user?.telegram_id) {
      toast.error("Пользователь не определён");
      return;
    }
    // Программы с гибкой настройкой (максимумы + дни) — через модалку
    if (tpl.requires_maxes) {
      setConfigTpl(tpl);
      return;
    }
    assign(tpl);
  };

  return (
    <div className="programs-page" data-testid="programs-page">
      <header className="programs-header">
        <Link to="/" className="programs-back" data-testid="programs-back" aria-label="Назад">
          <ArrowLeft size={22} />
        </Link>
        <h1 className="programs-title">Программы</h1>
      </header>

      <div className="programs-actions">
        <button
          className="programs-action"
          type="button"
          onClick={() => toast.info("Конструктор программ появится позже")}
        >
          <PencilLine size={18} />
          <span>Создать свою</span>
          <em>скоро</em>
        </button>
        <button
          className="programs-action"
          type="button"
          onClick={() => toast.info("Импорт из файла появится позже")}
        >
          <Upload size={18} />
          <span>Импорт из файла</span>
          <em>скоро</em>
        </button>
      </div>

      <h2 className="programs-section-title">Готовые программы</h2>

      {loading ? (
        <div className="programs-empty">Загрузка…</div>
      ) : templates.length === 0 ? (
        <div className="programs-empty">Программы не найдены</div>
      ) : (
        <div className="programs-list">
          {templates.map((tpl) => {
            const isActive = activePlan && activePlan.source_template_id === tpl.id;
            return (
              <div
                className={`program-card ${isActive ? "program-card-active" : ""}`}
                key={tpl.id}
                data-testid={`program-card-${tpl.slug || tpl.id}`}
              >
                <div className="program-card-head">
                  <div className="program-card-icon">
                    <Dumbbell size={20} />
                  </div>
                  <div className="program-card-titles">
                    <h3 className="program-card-name">{tpl.name}</h3>
                    <div className="program-card-badges">
                      <span className="badge">{LEVEL_LABELS[tpl.level] || tpl.level}</span>
                      <span className="badge">{GOAL_LABELS[tpl.goal] || tpl.goal}</span>
                    </div>
                  </div>
                </div>
                <p className="program-card-desc">{tpl.description}</p>
                <div className="program-card-meta">
                  <span>{tpl.weeks_count} нед.</span>
                  <span>·</span>
                  <span>{tpl.days_per_week} дн./нед.</span>
                </div>
                <button
                  className="program-card-button"
                  type="button"
                  onClick={() => handleChoose(tpl)}
                  disabled={assigningId === tpl.id || isActive}
                  data-testid={`choose-${tpl.slug || tpl.id}`}
                >
                  {isActive ? (
                    <>
                      <Check size={16} /> Активна
                    </>
                  ) : assigningId === tpl.id ? (
                    "Назначаем…"
                  ) : (
                    "Выбрать"
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {configTpl ? (
        <ProgramConfigModal
          tpl={configTpl}
          submitting={assigningId === configTpl.id}
          onClose={() => setConfigTpl(null)}
          onSubmit={(payload) => assign(configTpl, payload)}
        />
      ) : null}
    </div>
  );
};

export default Programs;
