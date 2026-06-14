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

const Programs = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activePlan, setActivePlan] = useState(null);
  const [assigningId, setAssigningId] = useState(null);

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

  const handleChoose = async (tpl) => {
    if (!user?.telegram_id) {
      toast.error("Пользователь не определён");
      return;
    }
    setAssigningId(tpl.id);
    try {
      const plan = await createPlan({
        athlete_telegram_id: user.telegram_id,
        template_id: tpl.id,
      });
      setActivePlan(plan);
      toast.success(`Программа «${tpl.name}» выбрана`);
      setTimeout(() => navigate("/"), 600);
    } catch (e) {
      toast.error("Не удалось выбрать программу");
    } finally {
      setAssigningId(null);
    }
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
    </div>
  );
};

export default Programs;
