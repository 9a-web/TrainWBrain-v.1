import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Globe, Send, Download, Dumbbell, CircleAlert, Check } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { getSharedProgram, importSharedProgram } from "@/api";
import { getEnv, hapticNotify } from "@/lib/platform";
import "./ImportLanding.css";

const LEVEL_LABELS = { beginner: "Новичок", intermediate: "Средний", advanced: "Продвинутый" };
const GOAL_LABELS = { strength: "Сила", hypertrophy: "Масса", powerlifting: "Пауэрлифтинг", general: "Общее" };

export default function ImportLanding() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const env = getEnv();

  const code = decodeURIComponent((location.pathname.split("/import/")[1] || "")).trim();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!code) {
      setError("Код не указан");
      return;
    }
    getSharedProgram(code)
      .then(setPreview)
      .catch((e) => {
        const d = e?.response?.data?.detail;
        setError(typeof d === "string" ? d : "Программа по этому коду не найдена");
      });
  }, [code]);

  const doImport = async () => {
    setImporting(true);
    try {
      const res = await importSharedProgram(code);
      hapticNotify("success");
      setDone(true);
      if (res.own) toast.info("Это ваша собственная программа");
      else if (res.already_imported) toast.info("Программа уже была импортирована");
      else toast.success(`«${res.template?.name}» добавлена в «Мои программы»`);
      setTimeout(() => navigate("/programs"), 900);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Не удалось импортировать");
      hapticNotify("error");
    } finally {
      setImporting(false);
    }
  };

  const continueOnSite = () => {
    try {
      window.localStorage.setItem("twb_pending_import", code);
    } catch (e) {
      /* no-op */
    }
    navigate("/");
  };

  return (
    <div className="il-page" data-testid="import-landing">
      <div className="il-ambient" aria-hidden="true" />
      <img src="/TWBlogo.png" alt="TrainWithBrain" className="il-logo" />

      {error ? (
        <div className="il-card il-card-error" data-testid="import-error">
          <CircleAlert size={26} />
          <h2>Программа не найдена</h2>
          <p>{error}</p>
          <button className="il-btn il-btn-secondary" onClick={() => navigate("/")}>На главную</button>
        </div>
      ) : !preview ? (
        <div className="il-card">
          <div className="il-skel" />
          <div className="il-skel il-skel-sm" />
        </div>
      ) : (
        <div className="il-card" data-testid="import-preview">
          <span className="il-badge">Вам поделились программой</span>
          <span className="il-ico"><Dumbbell size={24} /></span>
          <h2 className="il-name">{preview.name}</h2>
          <p className="il-author">от {preview.author_name}</p>
          {preview.description ? <p className="il-desc">{preview.description}</p> : null}
          <div className="il-meta">
            <span>{preview.weeks_count} нед.</span>
            <span>·</span>
            <span>{preview.days_per_week || "—"} дн./нед.</span>
            <span>·</span>
            <span>{preview.exercises_count} упражнений</span>
          </div>
          <div className="il-tags">
            <span className="il-tag">{LEVEL_LABELS[preview.level] || preview.level}</span>
            <span className="il-tag">{GOAL_LABELS[preview.goal] || preview.goal}</span>
            {preview.requires_maxes ? <span className="il-tag il-tag-accent">%1ПМ</span> : null}
          </div>

          {isAuthenticated ? (
            <button className="il-btn il-btn-primary" onClick={doImport}
              disabled={importing || done} data-testid="import-btn">
              {done ? (<><Check size={17} /> Импортировано</>)
                : importing ? "Импортируем…"
                : (<><Download size={17} /> Импортировать в мои программы</>)}
            </button>
          ) : (
            <>
              <p className="il-choose">Где открыть программу?</p>
              <button className="il-btn il-btn-primary" onClick={continueOnSite}
                data-testid="import-open-web">
                <Globe size={17} /> Продолжить на сайте
              </button>
              {preview.tg_link && env !== "telegram" ? (
                <a className="il-btn il-btn-tg" href={preview.tg_link} data-testid="import-open-tg">
                  <Send size={17} /> Открыть в Telegram
                </a>
              ) : null}
              <p className="il-note">Потребуется вход — после него импорт продолжится автоматически.</p>
            </>
          )}
        </div>
      )}

      <p className="il-code" data-testid="import-code">Код: {code || "—"}</p>
    </div>
  );
}
